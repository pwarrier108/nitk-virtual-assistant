import json
import csv
from pathlib import Path

# Load the JSON data from the file
file_path = Path(r"C:\Users\padma\Documents\Projects\nitkmodular\results\query_results.json")
with open(file_path, 'r') as file:
    data = json.load(file)

# Prepare CSV headers
headers = [
    "Query Text", "Doc Snippet", "Platform",
    "Initial Score", "Final Score", "Boost (Person)",
    "Boost (Org)", "Boost (Hashtag)", "Boost (Mentions)"
]

# Prepare CSV rows
rows = []
for query in data['queries']:
    query_text = query["query"]
    for result in query["results"]:
        doc_snippet = result["document"]
        platform = result["source"].get("platform", "N/A")
        initial_score = result["score_breakdown"]["initial_score"]
        final_score = result["score_breakdown"]["final_score"]
        boost_person = result["score_breakdown"].get("person_boost", 0.0)
        boost_org = result["score_breakdown"].get("entity_boost", 0.0)
        boost_hashtag = 0.0
        boost_mentions = 0.0

        # Extract boost details for hashtags and mentions
        for reason in result["score_breakdown"].get("metadata_reasons", []):
            if "hashtags" in reason:
                boost_hashtag = float(reason.split(": +")[-1])
            if "mentions" in reason:
                boost_mentions = float(reason.split(": +")[-1])

        rows.append([
            query_text, doc_snippet, platform, initial_score, final_score,
            boost_person, boost_org, boost_hashtag, boost_mentions
        ])

# Write to CSV
output_csv_path = Path(r"C:\Users\padma\Documents\Projects\nitkmodular\results\Query Results Analysis.csv")
with open(output_csv_path, mode="w", newline="", encoding="utf-8") as csvfile:
    writer = csv.writer(csvfile)
    writer.writerow(headers)
    writer.writerows(rows)

print(f"CSV saved to {output_csv_path}")
