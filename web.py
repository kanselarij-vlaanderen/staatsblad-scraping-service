from pytz import timezone as pytz_timezone
from helpers import logger
from flask import jsonify, request
from datetime import date, datetime, timezone
from staatsblad_api import request_decision_details, extract_decision_details, MalformedStaatsbladResponseException
from publication_flow import select_pending_pub_flows, insert_decision, link_decision

BRUSSELS_TZ = pytz_timezone('Europe/Brussels')

@app.route("/")
def hello():
    return "service is alive and kicking 😎"

@app.route("/run", methods=["POST"])
def run():
    now = datetime.now(timezone.utc).astimezone(BRUSSELS_TZ)
    today = date(now.year, now.month, now.day)
    pub_date = today
    pending_publications = select_pending_pub_flows()
    for pub_flow in pending_publications:
        try:
            if pub_flow['expected_pub_date']:
                expected_pub_day = date(pub_flow['expected_pub_date'].year,
                    pub_flow['expected_pub_date'].month,
                    pub_flow['expected_pub_date'].day)
                if expected_pub_day < today: # best we can try without random probing
                    try_pub_date = expected_pub_day
                else: # covers both cases with expected date today as in the future. Tries those expected in the future anyway in case of early publications (?)
                    try_pub_date = today
            else:
                try_pub_date = today
            root_elem = request_decision_details(pub_flow["numac"], try_pub_date)
        except MalformedStaatsbladResponseException:
            logger.warning(f"Failed getting valid api response for publication with numac {pub_flow['numac']} " + \
            f"(expected pub date {pub_flow['expected_pub_date'] if pub_flow['expected_pub_date'] else 'unknown'}). " + \
            "The Numac you requested probably just isn't published yet or invalid")
            continue
        except Exception:
            logger.exception(f"Failed getting valid api response for publication with numac {pub_flow['numac']}. " + \
            "Probably something went wrong while calling the staatsblad API.")
            continue
        responsible_entity, prom_date, title = extract_decision_details(root_elem)
        decision_uri = insert_decision(pub_flow["numac"], pub_date, responsible_entity, prom_date, title)
        modification_datetime = now
        link_decision(pub_flow["uri"], decision_uri, modification_datetime, pub_date)
    return "Finished linking"
        