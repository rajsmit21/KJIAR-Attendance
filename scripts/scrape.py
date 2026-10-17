import json
import re
import requests
from bs4 import BeautifulSoup

URL = "https://www.kjiar.edu.in/9-2-msr-ccim/attendance/students"
HEADERS = {"User-Agent": "Mozilla/5.0"}


def scrape():
  res = requests.get(URL, headers=HEADERS, timeout=30)
  soup = BeautifulSoup(res.text, "html.parser")

  # 1. Locate all month headers and their sibling tables
  # E.g., 'Attendance: September 2026', 'Attendance: August 2026', etc.
  students = {}

  month_headings = soup.find_all(
      lambda tag: tag.name in ["h2", "h3"] and "Attendance:" in tag.text
  )

  for heading in month_headings:
    month_name = (
        heading.text.replace("Attendance:", "").strip() or "Unknown Month"
    )
    table = heading.find_next("table")
    if not table:
      continue

    rows = table.find_all("tr")
    # Identify data rows (skip headers)
    for row in rows:
      cols = [td.get_text(strip=True) for td in row.find_all("td")]
      # A data row starts with roll number digit
      if not cols or not cols[0].isdigit() or len(cols) < 13:
        continue

      roll, enroll, name = cols[0], cols[1], cols[2]

      # Parse subjects: Rachana, Kriya, Samhita, Samskritam, Padartha
      # Each subject has 2 columns: Theory, NLHT+NLHP (Practical)
      try:
        data_points = [float(re.sub(r"[^\d.]", "", x) or 0) for x in cols[3:13]]
      except ValueError:
        continue

      if roll not in students:
        students[roll] = {
            "roll": int(roll),
            "enroll": enroll,
            "name": name,
            "months": {},
        }

      students[roll]["months"][month_name] = {
          "rachana": {"theory": data_points[0], "practical": data_points[1]},
          "kriya": {"theory": data_points[2], "practical": data_points[3]},
          "samhita": {"theory": data_points[4], "practical": data_points[5]},
          "samskritam": {
              "theory": data_points[6],
              "practical": data_points[7],
          },
          "padartha": {"theory": data_points[8], "practical": data_points[9]},
      }

  # 2. Compute Cumulative Averages for every student
  output = []
  for roll, s in sorted(students.items(), key=lambda x: int(x[0])):
    subjects = ["rachana", "kriya", "samhita", "samskritam", "padartha"]
    subject_sums = {sub: [] for sub in subjects}

    for month_data in s["months"].values():
      for sub in subjects:
        # Combined average of Theory & Practical for that month
        m_avg = (month_data[sub]["theory"] + month_data[sub]["practical"]) / 2.0
        subject_sums[sub].append(m_avg)

    sub_averages = {
        sub: round(sum(vals) / len(vals), 2) if vals else 0
        for sub, vals in subject_sums.items()
    }
    total_avg = (
        round(sum(sub_averages.values()) / len(sub_averages), 2)
        if sub_averages
        else 0
    )

    output.append({
        "roll": s["roll"],
        "enroll": s["enroll"],
        "name": s["name"],
        "subject_averages": sub_averages,
        "overall_average": total_avg,
        "eligible": total_avg >= 75.0,
        "monthly_breakdown": s["months"],
    })

  with open("attendance.json", "w", encoding="utf-8") as f:
    json.dump(
        {
            "last_updated": requests.utils.default_headers()[
                "User-Agent"
            ],  # replace with timestamp
            "students": output,
        },
        f,
        indent=2,
    )


if __name__ == "__main__":
  scrape()
