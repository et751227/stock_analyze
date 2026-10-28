"""DB-owned read projection. Intended for existing authenticated/private life-core API.
Do not expose this module as an unauthenticated VPS service.
"""
def latest_research(db, code):
    if not isinstance(code,str) or not code.isascii() or not code.isdigit() or not 4 <= len(code) <= 6:
        raise ValueError("invalid stock code")
    with db.cursor() as cursor:
        cursor.execute("""SELECT r.id,r.stock_code,r.market_date,r.completed_at,v.verdict,v.explanation
            FROM stock_research.runs r
            JOIN stock_research.verdicts v ON v.run_id=r.id
            WHERE r.stock_code=%s AND r.qc_status='QC_PASS'
            ORDER BY r.completed_at DESC,r.id DESC LIMIT 1""",(code,))
        run=cursor.fetchone()
        if not run:
            return None
        rid,stock_code,market_date,completed,verdict,explanation=run
        cursor.execute("""SELECT agent_role,ordinal,observed_fact,conditional_inference,unknown_fact
            FROM stock_research.agent_arguments WHERE run_id=%s
            ORDER BY agent_role,ordinal""",(rid,))
        arguments={"A":[],"B":[]}
        for role,ordinal,fact,inference,unknown in cursor.fetchall():
            arguments[role].append(f"{fact} {inference} （限制：{unknown}）")
        cursor.execute("""SELECT agent_role,total FROM stock_research.agent_scores WHERE run_id=%s""",(rid,))
        scores=dict(cursor.fetchall())
        cursor.execute("""SELECT horizon_trading_days,status,observed_market_date,return_pct
            FROM stock_research.outcomes WHERE run_id=%s ORDER BY horizon_trading_days""",(rid,))
        outcomes=[{"horizon_trading_days":h,"status":status,"observed_date":date.isoformat() if date else None,"return_pct":float(ret) if ret is not None else None} for h,status,date,ret in cursor.fetchall()]
    return {"code":stock_code,"market_date":market_date.isoformat(),"completed_at":completed.isoformat(),
            "status":"REAL_VERIFIED","A":{"score":scores.get("A"),"arguments":arguments["A"]},
            "B":{"score":scores.get("B"),"arguments":arguments["B"]},
            "verdict":{"result":verdict,"explanation":explanation},"outcomes":outcomes}
