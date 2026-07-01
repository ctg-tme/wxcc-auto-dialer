#!/usr/bin/env python3
"""
Script to check customerSentimentScore from WXCC Search API
Loops until first task has non-null customerSentimentScore
"""

import requests
import json
import time

# API Configuration
API_URL = "https://api.wxcc-eu2.cisco.com/search"
TOKEN = "eyJhbGciOiJSUzI1NiJ9.eyJjbHVzdGVyIjoiUEU5MyIsInByaXZhdGUiOiJleUpqZEhraU9pSktWMVFpTENKbGJtTWlPaUpCTVRJNFEwSkRMVWhUTWpVMklpd2lZV3huSWpvaVpHbHlJbjAuLnZTcm5LTzdrbVVvYU00T0hXUl9vamcuYTRLS2dwUXlySEJsbmt5T2tjaU9zTnVrdHQzeHp5OFFaektZU1I3cG5WVkJTaXhkZkxYbW96Y1hicXdkLWc5dG94TVlHclpEc1dqYnZkbUpBZXg0VF80MV9Rc1lMZ0tCYXM5QUNLM2Z3Ykl3Y216dl9XQVVQMG5xcVVHdE44WTRtakJIQVIzWURJMHZZcVRGZnBuR2QtX25JYjRJdWZMX3hKb3F3MXpsU3dmQmt3WlZ3M09EUXBvNVctRWt0VGs4cUZienBjOVVFRFpScFVkSUQ0NHNEUjhvaUpUU0NvR1RYS2dUaGdsX0N1YXl1R256NVBSdGx5QUNLMV9LLU91RkVUcjJUaXB2M1VJVmIzU3B4SFZ2RW9HbkhVNm1kU1pYdGpBdHFNOU1KY19pNVByN2hrcWh1Q3Z3Wms1bmdpZTF0WU9HNjhWUS02MzJGWElocER6N1hwV0xYdkt6NTFSRDZZZ29vUDVHQTlLWHBpa2pVVUVnVmIwV3lMcThRZHAxeDlKbHBxenRqWFNUNjlvQTZPV3dyZEZhaS1rMXYxQkxlek1jbGdkeVVGUHJiMnpiZDFJTDlqWC1VTVBDQXBaaEdZZks2SXd2SUNtNFVOLXJKYlFaVWxuZ01GcmlHbjhhc2w5RUQzYnNxbjJvTl9zaTFIYlZLVEtkMEhLRDFWcUJzS3BoR3NadkNHT0ZjaXJrZVBfNjJxTWFZUHNfV3N6TGNNQUFCMGw4SHV1OXNzRjVJeVZYNDVQQ0dCM0lBdmpjTHpnVGZseUVaYVdtbk54UkRTdU96OWo5Uk56YVpQdnBZd1h5ZWdWcFQ0dWZoRXdqQTZvWnA3aGNGeF9ZNG5pTEhyeUVvZXlCMHdaS1R3UVE1NllJTUw3WXo3YW90RW9WSERQR1o0RUtlUEE5cmVZcHBCNXJUZGpjeEZOZk5GRy1iV09Kd3BqUTRGUEJXZ19yaXk5UnJRdk5TbHNkLVNZa3F3M0hQbUpnTmxJS2JZNDZUWXZsS2RlODV2NUdLR1FvOXBCWWd3Qm1qOWJibm8yVVl3Wm8zakYzamNtbXp6OGNIeE1zbWdBUktFYWJhMnQ1NnFYRWljb09zTmlWWnEwWVgyRDNOanVNWnpCbVhqeU1jUWxONTRsUlFQV3hqeWhNbnBrZFR5dnc2SWVPdVJhbld5bkdfWk5pTXlzNGx4S1RRdnFOTk8zTVduc2FvMWVfcHllWXYwT2lkaUJXSnpGejFSSV85U1Y0VjdoRFRqYjFBamFYcVM4bzdqOTNuM241TDhESEJjSTYyLW1ldzB6RkpfTmZSbkhQOUVyWGRvSmtiaEU2M3FxNmlFVVcxM1VwUWhha3ZsOUpRdS1mc1dmRGtkd3hRU1R1LVg0QjNwelRkemdEZzltNVJjSDlTa3hkX3lFbXZYcmltc1JvTHVrenk5ampkR2JadE14V3NJbnYzYjg2dF9aTWswQmc1OVBsNUdmcFBCTDZic2lqQTFYT3RDdkZyU0JZVmhMNXRDUFdQZFpuWl9uQ05DaDU4alpjLkdJQmpfY2dNdzFLdThwQ2x4Y1RXMEEiLCJyZWZlcmVuY2VfaWQiOiI5MjI2MDczZi0zYTQ3LTQzYWItOGM5OC03ZTJjOWYwOGRiNWEiLCJhbXIiOlsicHdkIl0sImlzcyI6Imh0dHBzOi8vaWRicm9rZXItZXUud2ViZXguY29tL2lkYiIsInRva2VuX3R5cGUiOiJCZWFyZXIiLCJjbGllbnRfaWQiOiJDYmVkNDU0NTFmYTA0ZTJjZTNmNGNiNzg1NzhiMDZjOGZlZGRmYzNmY2U5NjEyYjlkMjQ1ZTFmM2FlNTNjYzQzOSIsInVzZXJfdHlwZSI6InVzZXIiLCJ0b2tlbl9pZCI6IkFhWjNyME5tVTRNRFZoTTJFdE1tWTNZUzAwT1dSakxUaGtOemN0T1dZd1pHVTRZakJtTTJNNE1tSmtObUl6TW1VdE5tSXoiLCJvcmdfaWQiOiJlNDA2MmViZS1lMjViLTQyZWYtYjExZi1hNGRjN2I1MDIyNzciLCJ1c2VyX21vZGlmeV90aW1lc3RhbXAiOiIyMDI2MDEyNjE2NTkwMS44MjRaIiwicmVhbG0iOiJlNDA2MmViZS1lMjViLTQyZWYtYjExZi1hNGRjN2I1MDIyNzciLCJjaXNfdXVpZCI6ImFjYjYwYTgyLWU5NDItNDhjNC1hMjJiLTY1NTJlZWYzOWQyOCIsImV4cGlyeV90aW1lIjoxNzcwNTI1MjY5MTM2LCJleHAiOjE3NzA1MjUyNjkxMzZ9.NTmkwZZLQK-jqNscKXb9jhTpg1QswZxp-IVJV6tSqJYa_DHLHerX_Zj7hbsm8MuCyoGvK6zrlYkJBKluD0IpjNyUjJFLEu-gfGDdCOWH67gk-q38qe8cIRFMfEby45Xpb1SbL6A6g84jChB60LVUapVrsmh9iNWa4Be9IPW75pHZ87M4B5JJz0wNiGHJm3Cwe-qDJM7r_YLMB8cTVTqituVCUzNyKAcWmceeZdGL9LNi3cuMwe4QTQ9-zMaCaifGGSXbrCH3SlMdxgLWWRSgpa_sL8O-xejSfG9SYNlcZj7eq7p0A_SQT8biC2HenFtVwmaETWG66WDAU2-3TLTLdw"

# GraphQL Query
QUERY = """
query TaskDetails(
  $from: Long!
  $to: Long!
  $pagination: Pagination
  $filter: TaskDetailsFilters
) {
  taskDetails(from: $from, to: $to, pagination: $pagination, filter: $filter) {
    tasks {
      id
      createdTime(sort: desc)
      autoEvalScore @include(if: true)
      customerSentimentScore @include(if: true)
    }
    pageInfo {
      endCursor
      hasNextPage
    }
  }
}
"""

# Variables
VARIABLES = {
    "from": 1770336000000,
    "to": 1770488807449,
    "pagination": {"cursor": "NA"},
    "filter": {
        "and": [
            {"id": {"notequals": ""}},
            {"isActive": {"equals": False}},
            {"lastQueue": {"name": {"contains": "EP_WX1"}}}
        ]
    }
}


def main():
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "query": QUERY,
        "variables": VARIABLES
    }
    
    attempt = 0
    
    while True:
        attempt += 1
        print(f"\n{'='*60}")
        print(f"ATTEMPT #{attempt}")
        print(f"{'='*60}")
        
        try:
            response = requests.post(API_URL, headers=headers, json=payload)
            
            # Log tracking ID from headers
            tracking_id = response.headers.get("trackingid", "N/A")
            print(f"Tracking ID: {tracking_id}")
            
            response.raise_for_status()
            
            data = response.json()
            
            if "errors" in data:
                print("GraphQL Errors:")
                for error in data["errors"]:
                    print(f"  - {error.get('message', error)}")
                time.sleep(1)
                continue
            
            tasks = data.get("data", {}).get("taskDetails", {}).get("tasks", [])
            
            print(f"Total tasks returned: {len(tasks)}")
            
            if not tasks:
                print("No tasks found, retrying...")
                time.sleep(1)
                continue
            
            # Check first task's customerSentimentScore
            first_task = tasks[0]
            task_id = first_task.get("id", "N/A")
            sentiment_score = first_task.get("customerSentimentScore")
            auto_eval_score = first_task.get("autoEvalScore")
            created_time = first_task.get("createdTime")
            
            print(f"\nFirst Task:")
            print(f"  ID: {task_id}")
            print(f"  Created Time: {created_time}")
            print(f"  customerSentimentScore: {sentiment_score} {'✓ NON-NULL!' if sentiment_score is not None else '✗ NULL'}")
            print(f"  autoEvalScore: {auto_eval_score}")
            
            # Check if first sentiment score is non-null
            if sentiment_score is not None:
                print(f"\n{'*'*60}")
                print(f"SUCCESS! First customerSentimentScore is NON-NULL: {sentiment_score}")
                print(f"Tracking ID: {tracking_id}")
                print(f"Task ID: {task_id}")
                print(f"Stopped after {attempt} attempt(s)")
                print(f"{'*'*60}")
                
                # Also log the first 3 tasks for context
                print("\nFirst 3 tasks:")
                for i, task in enumerate(tasks[:3]):
                    print(f"  {i+1}. ID: {task.get('id')}, Score: {task.get('customerSentimentScore')}")
                
                break
            
            print(f"\nFirst sentiment score is NULL, retrying in 1 second...")
            time.sleep(1)
                
        except requests.exceptions.RequestException as e:
            print(f"Request failed: {e}")
            time.sleep(1)
        except json.JSONDecodeError as e:
            print(f"Failed to parse response: {e}")
            time.sleep(1)


if __name__ == "__main__":
    main()
