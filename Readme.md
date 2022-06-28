# Staatsblad scraping service

Checks with Staatsblad api if pending Kaleidos publication-flows resulted in a publication today.  
Creates an `eli:LegalResource` under the `http://themis.vlaanderen.be`-namespace for each new publication and links the relevant publication-flow including a status-update for follow-up workflow.  

Uses Staatsblad endpoint `https://www.ejustice.just.fgov.be/cgi/api2.pl`.  

Note that the service creates `eli:LegalResource`'s under the Themis namespace while one would expect to link to resources in the `http://www.ejustice.just.fgov.be/eli/` namespace instead. Reasons for this approach are:
- ELI URI's under `http://www.ejustice.just.fgov.be/eli/` get generated 1 or more days after effective publication, while the HTML-api provides **realtime results**.
- As also mentioned in [lod-sbmb documentation](https://github.com/Fedict/lod-sbmb), only primary legislation gets an ELI-URI as identifier under the `http://www.ejustice.just.fgov.be/eli/` namespace. The ELI-listing endpoint thus only covers part of the publication-flows. The api used by this service on the other hand covers **áll publications**.

### REST API
#### POST /run

For each pending publication, check if it has been published in Staatsblad. If so, create and link to decision entity and update worklow statuses.

#### Related

Integrating ELI-identifiers: [Staatsblad linking service](https://github.com/kanselarij-vlaanderen/staatsblad-linking-service)