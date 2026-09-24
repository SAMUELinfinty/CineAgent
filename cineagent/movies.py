import csv
import os
import random

# Absolute or relative path to your CSV file
CSV_PATH = os.path.join(os.path.dirname(__file__), "Data", "watchlist.csv")

def load_movies_from_csv(file_path: str = CSV_PATH) -> list[dict]:
    """Reads the CSV file and returns a list of dictionaries for items with Title Type == 'Movie'."""
    movies = []
    if not os.path.exists(file_path):
        print(f"Warning: CSV file not found at {file_path}")
        return movies

    with open(file_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # IMDb exports may include shows as well as films.  The bot's
            # recommendations should honour its movie-only contract.
            if row.get("Title Type", "").strip().lower() not in ["movie", "tv series"]:
                continue

            title = (row.get("Title") or "").strip()
            if not title:
                continue
            movies.append({
                    "title": title,
                    "year": (row.get("Year") or "Unknown").strip(),
                    "genres": (row.get("Genres") or "Unknown").strip(),
                    "rating": (row.get("IMDb Rating") or "N/A").strip(),
                    "director": (row.get("Directors") or "Unknown").strip(),
                    "type": (row.get("Title Type") or "Movie").strip(),
                })
    return movies

def pick_recommendation(seen_titles: list[str], disliked_titles: list[str]) -> dict | None:
    """Selects an unseen, non-disliked movie from the CSV dataset."""
    all_movies = load_movies_from_csv()
    excluded = set(seen_titles + disliked_titles)
    
    # Filter candidates using list comprehension
    candidates = [m for m in all_movies if m["title"] not in excluded]
    
    # Fallback if all candidates are exhausted
    if not candidates and all_movies:
        candidates = all_movies

    return random.choice(candidates) if candidates else None

if __name__ == "__main__":
    rec = pick_recommendation(seen_titles=[], disliked_titles=[])
    print("Selected Movie:", rec)
