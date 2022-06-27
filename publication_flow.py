from string import Template
from datetime import datetime, date
from pytz import timezone as pytz_timezone
from helpers import generate_uuid
from escape_helpers import sparql_escape_uri, sparql_escape_string, sparql_escape_date, sparql_escape_datetime
from sudo_query import query, update
from query_util import result_to_records

BRUSSELS_TZ = pytz_timezone('Europe/Brussels')

def select_pending_pub_flows():
    q_string = """PREFIX dossier: <https://data.vlaanderen.be/ns/dossier#>
PREFIX adms: <http://www.w3.org/ns/adms#>
PREFIX eli: <http://data.europa.eu/eli/ontology#>
PREFIX prov: <http://www.w3.org/ns/prov#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
PREFIX pub: <http://mu.semte.ch/vocabularies/ext/publicatie/>
PREFIX tmo: <http://www.semanticdesktop.org/ontologies/2008/05/20/tmo#>

SELECT DISTINCT (?publicationFlow AS ?uri) ?numac ?expected_pub_date
WHERE {
    GRAPH <http://mu.semte.ch/graphs/organizations/kanselarij> {
        ?publicationFlow a pub:Publicatieaangelegenheid .
        ?publicationFlow pub:identifier / skos:notation ?numac .
        ?publicationFlow adms:status ?status .
        FILTER(?status != <http://themis.vlaanderen.be/id/concept/publicatie-status/2f8dc814-bd91-4bcf-a823-baf1cdc42475>)
        
        ?publicationFlow pub:doorlooptPublicatie ?publicationSubcase .
        
        ?publicationSubcase ^pub:publicatieVindtPlaatsTijdens ?publicationActivity .
        OPTIONAL { ?publicationSubcase tmo:targetEndTime ?expected_pub_date }
    }
    FILTER NOT EXISTS { ?publicationActivity prov:generated ?staatsbladDecision . }
}"""
    results = query(q_string)
    records = result_to_records(results)
    for r in records:
        if r["expected_pub_date"]:
            r["expected_pub_date"] = datetime.fromisoformat(r["expected_pub_date"].replace("Z", "+00:00"))
    return records

def insert_decision(numac, pub_date, responsible, prom_date=None, title=None):
    # TODO: make prom date and title optional
    LEGAL_RES_URI_BASE = "https://themis.vlaanderen.be/id/besluit/"
    uuid = generate_uuid()
    uri = LEGAL_RES_URI_BASE + uuid
    q_template = Template("""PREFIX eli: <http://data.europa.eu/eli/ontology#>
PREFIX mu: <http://mu.semte.ch/vocabularies/core/>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

INSERT DATA {
    GRAPH <http://mu.semte.ch/graphs/organizations/kanselarij> {
        $uri 
            a eli:LegalResource ;
            mu:uuid $uuid ;
            eli:id_local $numac ;
            $prom_date_statement
            $title_statement
            eli:date_publication $pub_date ;
            eli:responsibility_of $responsible .
    }
}""")
    q_string = q_template.substitute(
        uri=sparql_escape_uri(uri),
        uuid=sparql_escape_string(uuid),
        numac=sparql_escape_string(numac),
        prom_date_statement=f"eli:date_document {sparql_escape_date(prom_date)} ;" if prom_date else "",
        title_statement=f"eli:title {sparql_escape_string(title)} ;" if title else "",
        pub_date=sparql_escape_date(pub_date),
        responsible=sparql_escape_string(responsible)
    )
    update(q_string)
    return uri

def link_decision(pubflow_uri, decision_uri, modification_datetime, publication_date):
    PUBLICATION_STATUS_MOD_BASE_URI = "http://themis.vlaanderen.be/id/publicatie-status-wijziging/"
    pub_stat_mod_uuid = generate_uuid()
    pub_stat_mod_uri = PUBLICATION_STATUS_MOD_BASE_URI + pub_stat_mod_uuid

    q_template = Template("""PREFIX dossier: <https://data.vlaanderen.be/ns/dossier#>
PREFIX adms: <http://www.w3.org/ns/adms#>
PREFIX eli: <http://data.europa.eu/eli/ontology#>
PREFIX prov: <http://www.w3.org/ns/prov#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
PREFIX pub: <http://mu.semte.ch/vocabularies/ext/publicatie/>
PREFIX mu: <http://mu.semte.ch/vocabularies/core/>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

DELETE {
    GRAPH <http://mu.semte.ch/graphs/organizations/kanselarij> {
        $pub_flow_uri adms:status ?publicationStatus .
        $pub_flow_uri prov:hadActivity ?oldPubStatusChange .
        ?oldPubStatusChange ?oldPubStatusChangePred ?oldPubStatusChangeObj .
    }
}
INSERT {
    GRAPH <http://mu.semte.ch/graphs/organizations/kanselarij> {
        $pub_flow_uri adms:status <http://themis.vlaanderen.be/id/concept/publicatie-status/2f8dc814-bd91-4bcf-a823-baf1cdc42475> ;
            dossier:sluitingsdatum $case_close_date ;
            prov:hadActivity $pub_stat_mod_uri .
        $pub_stat_mod_uri a pub:PublicatieStatusWijziging ;
            mu:uuid $pub_stat_mod_uuid ;
            prov:startedAtTime $mod_datetime .
        ?publicationActivity prov:generated $decision_uri ;
            dossier:Activiteit.einddatum $pub_act_end_time .
        ?publicationSubcase dossier:Procedurestap.einddatum $pub_subc_end_time .
    }
}
WHERE {
    GRAPH <http://mu.semte.ch/graphs/organizations/kanselarij> {
        $pub_flow_uri
            a pub:Publicatieaangelegenheid ;
            adms:status ?publicationStatus .
        FILTER(?publicationStatus != <http://themis.vlaanderen.be/id/concept/publicatie-status/2f8dc814-bd91-4bcf-a823-baf1cdc42475>)
        OPTIONAL {
            $pub_flow_uri prov:hadActivity ?oldPubStatusChange .
            ?oldPubStatusChange
                a pub:PublicatieStatusWijziging ;
                ?oldPubStatusChangePred ?oldPubStatusChangeObj .
        }

        $pub_flow_uri pub:doorlooptPublicatie ?publicationSubcase .

        ?publicationSubcase ^pub:publicatieVindtPlaatsTijdens ?publicationActivity .
    }
}""")
    q_string = q_template.substitute(pub_flow_uri=sparql_escape_uri(pubflow_uri),
        case_close_date=sparql_escape_date(date(modification_datetime.year, modification_datetime.month, modification_datetime.day)),
        pub_stat_mod_uri=sparql_escape_uri(pub_stat_mod_uri),
        pub_stat_mod_uuid=sparql_escape_string(pub_stat_mod_uuid),
        pub_act_end_time=sparql_escape_datetime(BRUSSELS_TZ.localize(datetime(publication_date.year, publication_date.month, publication_date.day))),
        pub_subc_end_time=sparql_escape_datetime(BRUSSELS_TZ.localize(datetime(publication_date.year, publication_date.month, publication_date.day))),
        mod_datetime=sparql_escape_datetime(modification_datetime),
        decision_uri=sparql_escape_uri(decision_uri))
    update(q_string)