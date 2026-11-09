// E-mail when the api or the worker logs an error (quota used up, a failed
// pipeline, an unhandled exception) or marks submissions as stuck.
// docs/AZURE.md, section "Observabilidad", says what to do with one.
param location string
param workspaceName string
param contactEmail string

resource workspace 'Microsoft.OperationalInsights/workspaces@2023-09-01' existing = {
  name: workspaceName
}

resource emailGroup 'Microsoft.Insights/actionGroups@2023-01-01' = {
  name: 'ag-fakesnews-email'
  location: 'global'
  properties: {
    groupShortName: 'fakesnews'
    enabled: true
    emailReceivers: [
      { name: 'owner', emailAddress: contactEmail, useCommonAlertSchema: true }
    ]
  }
}

// Only JSON lines with an event: the plain-text tracebacks a worker prints
// while shutting down (Redis already gone) are noise, not errors.
var errorsQuery = '''
ContainerAppConsoleLogs_CL
| where ContainerAppName_s in ('ca-fakesnews-api', 'ca-fakesnews-worker')
| extend j = parse_json(Log_s)
| where isnotempty(tostring(j.event))
| where tostring(j.level) == 'error' or tostring(j.event) == 'submissions_marked_stuck'
| summarize n = count() by event = tostring(j.event)
'''

// Hourly: the cheapest price tier (15 minutes or more), 0.50 USD a month.
resource errorsAlert 'Microsoft.Insights/scheduledQueryRules@2023-03-15-preview' = {
  name: 'alert-fakesnews-errors'
  location: location
  properties: {
    displayName: 'FakesNews: errores en la API o el worker'
    description: 'La API o el worker registraron un error o casos atascados. La consulta dice qué evento y cuántas veces. Qué hacer: docs/AZURE.md, sección Observabilidad.'
    severity: 2
    enabled: true
    scopes: [workspace.id]
    evaluationFrequency: 'PT1H'
    windowSize: 'PT1H'
    criteria: {
      allOf: [
        {
          query: errorsQuery
          timeAggregation: 'Count'
          operator: 'GreaterThan'
          threshold: 0
          failingPeriods: { numberOfEvaluationPeriods: 1, minFailingPeriodsToAlert: 1 }
        }
      ]
    }
    // One e-mail, then quiet for 6 hours while the same problem lasts.
    muteActionsDuration: 'PT6H'
    autoMitigate: false
    actions: { actionGroups: [emailGroup.id] }
  }
}
