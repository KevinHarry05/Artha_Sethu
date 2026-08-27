"""
Offline, approximate India gazetteer — states/UTs, major cities, and a
sample of well-known localities in the top metros. Used only as a
fallback when a query doesn't match the curated 200-location Tamil Nadu
dataset (db/ingest_raw_data.py).

Honesty note, matching the rest of this project's data discipline: these
coordinates are illustrative approximations (city/state centroids from
general knowledge, not a surveyed gazetteer), and any location resolved
through this file — or through modules/location_resolver/synth.py's final
catch-all — carries data_source = 'auto_generated_synthetic_no_ground_truth'
downstream. Never presented as sourced Census/LGD data. This is what makes
"give it Koramangala" or "give it any district" not crash, at the honestly
disclosed cost of that location's numbers being illustrative, same as the
rest of this dataset already is per docs/DATA_DECISIONS.md.
"""

# state/UT -> (capital_city, district_label, lat, lon)
INDIAN_STATES = {
    "andhra pradesh": ("Vijayawada", "Krishna", 16.5062, 80.6480),
    "arunachal pradesh": ("Itanagar", "Papum Pare", 27.0844, 93.6053),
    "assam": ("Guwahati", "Kamrup Metropolitan", 26.1445, 91.7362),
    "bihar": ("Patna", "Patna", 25.5941, 85.1376),
    "chhattisgarh": ("Raipur", "Raipur", 21.2514, 81.6296),
    "goa": ("Panaji", "North Goa", 15.4909, 73.8278),
    "gujarat": ("Gandhinagar", "Gandhinagar", 23.2156, 72.6369),
    "haryana": ("Chandigarh", "Chandigarh", 30.7333, 76.7794),
    "himachal pradesh": ("Shimla", "Shimla", 31.1048, 77.1734),
    "jharkhand": ("Ranchi", "Ranchi", 23.3441, 85.3096),
    "karnataka": ("Bengaluru", "Bengaluru Urban", 12.9716, 77.5946),
    "kerala": ("Thiruvananthapuram", "Thiruvananthapuram", 8.5241, 76.9366),
    "madhya pradesh": ("Bhopal", "Bhopal", 23.2599, 77.4126),
    "maharashtra": ("Mumbai", "Mumbai Suburban", 19.0760, 72.8777),
    "manipur": ("Imphal", "Imphal West", 24.8170, 93.9368),
    "meghalaya": ("Shillong", "East Khasi Hills", 25.5788, 91.8933),
    "mizoram": ("Aizawl", "Aizawl", 23.7271, 92.7176),
    "nagaland": ("Kohima", "Kohima", 25.6751, 94.1086),
    "odisha": ("Bhubaneswar", "Khordha", 20.2961, 85.8245),
    "punjab": ("Chandigarh", "Chandigarh", 30.7333, 76.7794),
    "rajasthan": ("Jaipur", "Jaipur", 26.9124, 75.7873),
    "sikkim": ("Gangtok", "East Sikkim", 27.3389, 88.6065),
    "tamil nadu": ("Chennai", "Chennai", 13.0827, 80.2707),
    "telangana": ("Hyderabad", "Hyderabad", 17.3850, 78.4867),
    "tripura": ("Agartala", "West Tripura", 23.8315, 91.2868),
    "uttar pradesh": ("Lucknow", "Lucknow", 26.8467, 80.9462),
    "uttarakhand": ("Dehradun", "Dehradun", 30.3165, 78.0322),
    "west bengal": ("Kolkata", "Kolkata", 22.5726, 88.3639),
    "delhi": ("New Delhi", "New Delhi", 28.7041, 77.1025),
    "jammu and kashmir": ("Srinagar", "Srinagar", 34.0837, 74.7973),
    "ladakh": ("Leh", "Leh", 34.1526, 77.5771),
    "puducherry": ("Puducherry", "Puducherry", 11.9416, 79.8083),
    "chandigarh": ("Chandigarh", "Chandigarh", 30.7333, 76.7794),
    "andaman and nicobar islands": ("Port Blair", "South Andaman", 11.6234, 92.7265),
}

# city (lowercase) -> (display_name, state, district, lat, lon)
MAJOR_CITIES = {
    "bengaluru": ("Bengaluru", "Karnataka", "Bengaluru Urban", 12.9716, 77.5946),
    "bangalore": ("Bengaluru", "Karnataka", "Bengaluru Urban", 12.9716, 77.5946),
    "mumbai": ("Mumbai", "Maharashtra", "Mumbai Suburban", 19.0760, 72.8777),
    "bombay": ("Mumbai", "Maharashtra", "Mumbai Suburban", 19.0760, 72.8777),
    "delhi": ("New Delhi", "Delhi", "New Delhi", 28.7041, 77.1025),
    "new delhi": ("New Delhi", "Delhi", "New Delhi", 28.7041, 77.1025),
    "chennai": ("Chennai", "Tamil Nadu", "Chennai", 13.0827, 80.2707),
    "madras": ("Chennai", "Tamil Nadu", "Chennai", 13.0827, 80.2707),
    "hyderabad": ("Hyderabad", "Telangana", "Hyderabad", 17.3850, 78.4867),
    "kolkata": ("Kolkata", "West Bengal", "Kolkata", 22.5726, 88.3639),
    "calcutta": ("Kolkata", "West Bengal", "Kolkata", 22.5726, 88.3639),
    "pune": ("Pune", "Maharashtra", "Pune", 18.5204, 73.8567),
    "ahmedabad": ("Ahmedabad", "Gujarat", "Ahmedabad", 23.0225, 72.5714),
    "surat": ("Surat", "Gujarat", "Surat", 21.1702, 72.8311),
    "nagpur": ("Nagpur", "Maharashtra", "Nagpur", 21.1458, 79.0882),
    "kanpur": ("Kanpur", "Uttar Pradesh", "Kanpur Nagar", 26.4499, 80.3319),
    "coimbatore": ("Coimbatore", "Tamil Nadu", "Coimbatore", 11.0168, 76.9558),
    "kochi": ("Kochi", "Kerala", "Ernakulam", 9.9312, 76.2673),
    "cochin": ("Kochi", "Kerala", "Ernakulam", 9.9312, 76.2673),
    "visakhapatnam": ("Visakhapatnam", "Andhra Pradesh", "Visakhapatnam", 17.6868, 83.2185),
    "indore": ("Indore", "Madhya Pradesh", "Indore", 22.7196, 75.8577),
    "nashik": ("Nashik", "Maharashtra", "Nashik", 19.9975, 73.7898),
    "vadodara": ("Vadodara", "Gujarat", "Vadodara", 22.3072, 73.1812),
    "ludhiana": ("Ludhiana", "Punjab", "Ludhiana", 30.9010, 75.8573),
    "agra": ("Agra", "Uttar Pradesh", "Agra", 27.1767, 78.0081),
    "varanasi": ("Varanasi", "Uttar Pradesh", "Varanasi", 25.3176, 82.9739),
    "amritsar": ("Amritsar", "Punjab", "Amritsar", 31.6340, 74.8723),
    "mysuru": ("Mysuru", "Karnataka", "Mysuru", 12.2958, 76.6394),
    "mysore": ("Mysuru", "Karnataka", "Mysuru", 12.2958, 76.6394),
    "madurai": ("Madurai", "Tamil Nadu", "Madurai", 9.9252, 78.1198),
    "jodhpur": ("Jodhpur", "Rajasthan", "Jodhpur", 26.2389, 73.0243),
    "guwahati": ("Guwahati", "Assam", "Kamrup Metropolitan", 26.1445, 91.7362),
    "noida": ("Noida", "Uttar Pradesh", "Gautam Buddha Nagar", 28.5355, 77.3910),
    "gurugram": ("Gurugram", "Haryana", "Gurugram", 28.4595, 77.0266),
    "gurgaon": ("Gurugram", "Haryana", "Gurugram", 28.4595, 77.0266),
    "faridabad": ("Faridabad", "Haryana", "Faridabad", 28.4089, 77.3178),
    "thane": ("Thane", "Maharashtra", "Thane", 19.2183, 72.9781),
}

# locality (lowercase) -> city key (must exist in MAJOR_CITIES)
LOCALITY_TO_CITY = {
    # Bengaluru
    "koramangala": "bengaluru", "indiranagar": "bengaluru", "whitefield": "bengaluru",
    "hsr layout": "bengaluru", "electronic city": "bengaluru", "jayanagar": "bengaluru",
    "malleshwaram": "bengaluru", "btm layout": "bengaluru", "marathahalli": "bengaluru",
    "yelahanka": "bengaluru",
    # Mumbai
    "andheri": "mumbai", "bandra": "mumbai", "powai": "mumbai", "dadar": "mumbai",
    "borivali": "mumbai", "malad": "mumbai", "juhu": "mumbai", "worli": "mumbai",
    "chembur": "mumbai", "goregaon": "mumbai",
    # Delhi
    "dwarka": "delhi", "saket": "delhi", "rohini": "delhi", "karol bagh": "delhi",
    "connaught place": "delhi", "vasant kunj": "delhi", "lajpat nagar": "delhi",
    "pitampura": "delhi", "janakpuri": "delhi", "mayur vihar": "delhi",
    # Chennai
    "t nagar": "chennai", "adyar": "chennai", "velachery": "chennai", "anna nagar": "chennai",
    "mylapore": "chennai", "tambaram": "chennai", "porur": "chennai", "guindy": "chennai",
    # Hyderabad
    "banjara hills": "hyderabad", "gachibowli": "hyderabad", "madhapur": "hyderabad",
    "kukatpally": "hyderabad", "secunderabad": "hyderabad", "ameerpet": "hyderabad",
    "kondapur": "hyderabad",
    # Kolkata
    "salt lake": "kolkata", "park street": "kolkata", "howrah": "kolkata",
    "ballygunge": "kolkata", "behala": "kolkata", "rajarhat": "kolkata",
    # Pune
    "koregaon park": "pune", "hinjewadi": "pune", "kothrud": "pune",
    "viman nagar": "pune", "baner": "pune", "wakad": "pune",
    # Ahmedabad
    "navrangpura": "ahmedabad", "satellite": "ahmedabad", "vastrapur": "ahmedabad",
    "bopal": "ahmedabad", "maninagar": "ahmedabad",
}
