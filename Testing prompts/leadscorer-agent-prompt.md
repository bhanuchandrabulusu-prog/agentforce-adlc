Build me an Agentforce employee agent called "LeadScorer" on my-dev-org.

Purpose: Internal sales team agent that summarizes lead information and 
classifies leads as High Value, Medium, or Low based on scoring criteria.

What the agent should do:

1. Summarize a single lead — When a user asks "summarize lead [name or ID]", 
   pull the lead record and present a summary of key fields: Name, Company, 
   Title, Email, Phone, LeadSource, Status, Industry, AnnualRevenue, 
   NumberOfEmployees. Then score and classify the lead.

2. Score recent leads — When a user asks "score my recent leads", pull the 
   10 most recent leads and return a summary table with Name, Company, 
   and Score.

3. Scoring rules (deterministic, not LLM-decided):
   - High: AnnualRevenue > 1,000,000 OR NumberOfEmployees > 500
   - Medium: AnnualRevenue between 100,000–1,000,000 OR NumberOfEmployees 50–500
   - Low: everything else

4. After scoring, write the result to a new custom field Lead.Lead_Score__c 
   (picklist with values: High, Medium, Low). This field does not exist yet — 
   scaffold it.

AnnualRevenue and NumberOfEmployees are standard Lead fields — do not scaffold 
those.

Agent type: Employee agent (internal use only, no messaging channel, 
no default_agent_user)
Org alias: my-dev-org
Action implementations: Generate new Apex stubs (Path C)
