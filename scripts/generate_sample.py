import json
from pathlib import Path


def main() -> None:
    root = Path("sample-folder")
    for directory in (
        "Work/Contracts",
        "Work/Reports",
        "Personal/Travel",
        "Personal/Medical",
    ):
        (root / directory).mkdir(parents=True, exist_ok=True)

    files = {
        "quarterly-business-review.txt": (
            "Agenda for the quarterly business review: revenue, delivery milestones, and hiring."
        ),
        "vaccination-record.txt": (
            "Personal immunization record with vaccination dates and clinic information."
        ),
        "unclassifiable-archive.xyz": bytes(range(256)) * 4,
        "Work/vendor-agreement.md": (
            "# Vendor services agreement\nContract terms, signatures, and renewal date."
        ),
        "Work/q3-metrics.csv": "metric,value\nrevenue,420000\nactive_users,1800\n",
        "Personal/flight-itinerary.html": (
            "<html><body><h1>Flight itinerary</h1><p>Departure and hotel booking.</p></body></html>"
        ),
        "Personal/lab-results.json": json.dumps(
            {"document": "medical laboratory results", "status": "normal"}
        ),
    }
    for relative_path, content in files.items():
        path = root / relative_path
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content, encoding="utf-8")

    manifest = {
        "expected": {
            "quarterly-business-review.txt": "Work",
            "vaccination-record.txt": "Personal",
            "unclassifiable-archive.xyz": None,
            "Work/vendor-agreement.md": "Work/Contracts",
            "Work/q3-metrics.csv": "Work/Reports",
            "Personal/flight-itinerary.html": "Personal/Travel",
            "Personal/lab-results.json": "Personal/Medical",
        }
    }
    Path("sample-manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
