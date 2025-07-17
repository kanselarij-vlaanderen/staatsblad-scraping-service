from io import StringIO
from datetime import date
from requests import get
from lxml import etree
from helpers import logger

class MalformedStaatsbladResponseException(Exception):
    pass

DUTCH_MONTHS = {
    "januari": 1,
    "februari": 2,
    "maart": 3,
    "april": 4,
    "mei": 5,
    "juni": 6,
    "juli": 7,
    "augustus": 8,
    "september": 9,
    "oktober": 10,
    "november": 11,
    "december": 12
}

parser = etree.HTMLParser()

API_BASE_URL = "https://www.ejustice.just.fgov.be/cgi/api2.pl?lg=N"

def request_decision_details(numac, pub_date):
    formatted_pub_date = pub_date.strftime("%Y-%m-%d")
    req_url = API_BASE_URL + f"&pd={formatted_pub_date}" + f"&numac={numac}"
    logger.debug(f"requesting url {req_url}")
    response = get(req_url)
    content = response.text

    tree = etree.parse(StringIO(content), parser)
    root = tree.getroot()

    # The endpoint doesn't differentiate between empty and valid responses by means
    # of HTTP status codes. below xpath expression is used to determine if response is valid instead
    # it looks for a unique link element that is only present on published items
    pub_link_elems = root.xpath(f"//a[@id=\"link-text\" and contains(text(), \"{numac}\")]")
    is_published = bool(pub_link_elems)

    if is_published:
        return root
    else:
        raise MalformedStaatsbladResponseException(f"Invalid response for page with publication date {pub_date} and numac {numac}")

def extract_decision_details(root):
    full_title = root.xpath("//div[@class=\"page__section page__section--top\"]/p[@class=\"intro-text\"]/text()")[0].strip()
    try:
        formatted_prom_date, title = full_title.split(". - ") # 21 SEPTEMBER 2021. - Nationale Orden
        prom_d, prom_m, prom_y = formatted_prom_date.split(" ") # 21 SEPTEMBER 2021
        prom_date = date(int(prom_y), DUTCH_MONTHS[prom_m.lower()], int(prom_d))
    except ValueError: # https://www.ejustice.just.fgov.be/cgi/api2.pl?lg=N&pd=2022-05-24&numac=2022020908
        prom_date = None
        title = None
    responsible_entity = root.xpath("//div[@class=\"page__section page__section--top\"]/h1[@class=\"page__title\"]/span/text()")[0].strip()
    return responsible_entity, prom_date, title
