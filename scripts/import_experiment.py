"""Import a validated three-agent experiment once, with no network or AI calls.

Usage (after migration and backup gate):
  STOCK_RESEARCH_DSN=... python scripts/import_experiment.py /private/path/experiment.json
Default without --apply is offline validation only.
"""
import argparse
import hashlib
import json
import pathlib
from datetime import date
from decimal import Decimal


def normalize(doc):
    assert doc["status"] == "completed_real_execution"
    src = doc["source"]
    row = src["record"]
    assert src["http_status"] == 200 and row["Code"].isdigit()
    assert src["market_date"] == date(int(row["Date"][:3])+1911,int(row["Date"][3:5]),int(row["Date"][5:7])).isoformat()
    assert len(src["sha256"]) == 64 and all(c in "0123456789abcdef" for c in src["sha256"].lower())
    result = doc["agents"]["C"]["response"]
    scores = {}
    for role in ("A","B"):
        values = result["scores"][role]
        expected = sum(values[x]["score"] for x in ("evidence_fidelity","inference_quality","counterevidence_handling","falsifiability"))
        assert expected == values["total"] and 0 <= expected <= 100
        scores[role] = values
    threshold = int(doc["protocol"]["tie_rule"].split("<=")[1].split(":")[0].strip())
    assert result["verdict"]["score_difference"] == abs(scores["A"]["total"]-scores["B"]["total"])
    if abs(scores["A"]["total"]-scores["B"]["total"]) <= threshold:
        assert result["verdict"]["result"] == "無定論"
    key = f'{row["Code"]}:{src["market_date"]}:{doc["completed_at"]}'
    return {"run_key":key,"row":row,"source":src,"doc":doc,"scores":scores,"threshold":threshold}


def apply(db, normalized):
    from psycopg.types.json import Jsonb
    d, src, row = normalized["doc"], normalized["source"], normalized["row"]
    with db.transaction():
        snap=db.execute("""INSERT INTO stock_research.source_snapshots
        (source_id,stock_code,market_date,retrieved_at,source_url,sha256,raw_record,open_price,high_price,low_price,close_price,trade_volume)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT(source_id,stock_code,market_date,sha256) DO UPDATE SET sha256=EXCLUDED.sha256 RETURNING id""",
        (src["id"],row["Code"],src["market_date"],src["retrieved_at"],src["url"],src["sha256"],Jsonb(row),
         Decimal(row["OpeningPrice"]),Decimal(row["HighestPrice"]),Decimal(row["LowestPrice"]),Decimal(row["ClosingPrice"]),int(row["TradeVolume"]))).fetchone()[0]
        found=db.execute("SELECT id FROM stock_research.runs WHERE run_key=%s",(normalized["run_key"],)).fetchone()
        if found:
            return found[0],False
        run=db.execute("""INSERT INTO stock_research.runs
          (run_key,stock_code,market_date,completed_at,snapshot_id,research_status,horizon_trading_days,qc_status)
          VALUES (%s,%s,%s,%s,%s,'COMPLETED',%s,'QC_PASS') RETURNING id""",
          (normalized["run_key"],row["Code"],src["market_date"],d["completed_at"],snap,20)).fetchone()[0]
        for role in ("A","B"):
            for index,arg in enumerate(d["agents"][role]["response"]["arguments"],1):
                db.execute("""INSERT INTO stock_research.agent_arguments
                  (run_id,agent_role,ordinal,observed_fact,conditional_inference,unknown_fact)
                  VALUES(%s,%s,%s,%s,%s,%s)""",
                  (run,role,index,arg["observed_fact"],arg["conditional_inference"],arg["unknown"]))
            scores=normalized["scores"][role]
            db.execute("""INSERT INTO stock_research.agent_scores
              (run_id,agent_role,evidence_fidelity,inference_quality,counterevidence_handling,falsifiability)
              VALUES(%s,%s,%s,%s,%s,%s)""",
              (run,role,*(scores[x]["score"] for x in ("evidence_fidelity","inference_quality","counterevidence_handling","falsifiability"))))
        verdict=d["agents"]["C"]["response"]["verdict"]
        db.execute("INSERT INTO stock_research.verdicts(run_id,verdict,tie_threshold,explanation) VALUES(%s,%s,%s,%s)",
                   (run,verdict["result"],normalized["threshold"],verdict["explanation"]))
        db.execute("INSERT INTO stock_research.outcomes(run_id,horizon_trading_days,status) VALUES(%s,20,'PENDING')",(run,))
    return run,True


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("experiment",type=pathlib.Path)
    ap.add_argument("--apply",action="store_true")
    args=ap.parse_args()
    doc=json.loads(args.experiment.read_text(encoding="utf-8"))
    normalized=normalize(doc)
    print(json.dumps({"valid":True,"run_key":normalized["run_key"],"source_sha256":normalized["source"]["sha256"],"apply":args.apply},ensure_ascii=False))
    if args.apply:
        import os
        import psycopg
        dsn=os.environ.get("STOCK_RESEARCH_DSN")
        if not dsn:
            raise RuntimeError("Missing STOCK_RESEARCH_DSN; no write attempted")
        with psycopg.connect(dsn,connect_timeout=10) as db:
            run,created=apply(db,normalized)
            count=db.execute("SELECT count(*) FROM stock_research.agent_arguments WHERE run_id=%s",(run,)).fetchone()[0]
            assert count == len(doc["agents"]["A"]["response"]["arguments"])+len(doc["agents"]["B"]["response"]["arguments"])
            print(json.dumps({"run_id":run,"created":created,"argument_count":count}))


if __name__=="__main__":
    main()
