"""
AI Flight Search Agent - Fixed Flight Loading
"""

import os
from datetime import datetime, timedelta
import json
from anthropic import Anthropic
import requests
from flask import Flask, request, jsonify, send_from_directory

app = Flask(__name__, static_folder='.')
client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

class FlightSearchAgent:
    def __init__(self):
        self.serpapi_key = os.environ.get("SERPAPI_KEY")
        
    def search_flights(self, origin, destination, outbound_date, return_date=None):
        params = {
            "engine": "google_flights",
            "departure_id": origin,
            "arrival_id": destination,
            "outbound_date": outbound_date,
            "currency": "GBP",
            "hl": "en",
            "api_key": self.serpapi_key
        }
        
        if return_date:
            params["return_date"] = return_date
            params["type"] = "1"
        
        try:
            response = requests.get("https://serpapi.com/search", params=params)
            data = response.json()
            print(f"Flight search response keys: {data.keys()}")  # Debug
            return data
        except Exception as e:
            print(f"Flight search error: {e}")
            return {"error": str(e)}
    
    def search_hotels(self, destination, check_in, check_out):
        params = {
            "engine": "google_hotels",
            "q": destination,
            "check_in_date": check_in,
            "check_out_date": check_out,
            "currency": "GBP",
            "gl": "uk",
            "hl": "en",
            "api_key": self.serpapi_key
        }
        
        try:
            response = requests.get("https://serpapi.com/search", params=params)
            return response.json()
        except Exception as e:
            return {"error": str(e)}
    
    def search_airbnb(self, destination, check_in, check_out):
        params = {
            "engine": "airbnb",
            "location": destination,
            "check_in": check_in,
            "check_out": check_out,
            "currency": "GBP",
            "api_key": self.serpapi_key
        }
        
        try:
            response = requests.get("https://serpapi.com/search", params=params)
            return response.json()
        except Exception as e:
            return {"error": str(e)}
    
    def parse_time(self, time_str):
        """Parse time string to hours"""
        if not time_str or time_str == "TBD":
            return 12  # Default to noon
        try:
            time_str = str(time_str).strip()
            if 'AM' in time_str or 'PM' in time_str:
                time_obj = datetime.strptime(time_str, "%I:%M %p")
            else:
                time_obj = datetime.strptime(time_str, "%H:%M")
            return time_obj.hour + time_obj.minute / 60
        except:
            return 12
    
    def analyze_flexible_dates(self, origin, destination, start_date, return_date, days_range=7):
        """Search flights across flexible dates"""
        results = []
        base_date = datetime.strptime(start_date, "%Y-%m-%d")
        
        if return_date:
            return_date_obj = datetime.strptime(return_date, "%Y-%m-%d")
        else:
            return_date_obj = None
        
        for i in range(days_range):
            search_date = (base_date + timedelta(days=i)).strftime("%Y-%m-%d")
            search_return = (return_date_obj + timedelta(days=i)).strftime("%Y-%m-%d") if return_date_obj else None
            
            flight_data = self.search_flights(origin, destination, search_date, search_return)
            
            # Handle both "best_flights" and "other_flights" from SerpAPI
            all_flights = []
            if "best_flights" in flight_data:
                all_flights.extend(flight_data.get("best_flights", []))
            if "other_flights" in flight_data:
                all_flights.extend(flight_data.get("other_flights", []))
            
            print(f"Date {search_date}: Found {len(all_flights)} flights")  # Debug
            
            for flight in all_flights:
                outbound_flights = flight.get("flights", [])
                
                # Extract timing info
                outbound_dep_time = "TBD"
                outbound_arr_time = "TBD"
                return_dep_time = "TBD"
                return_arr_time = "TBD"
                
                if outbound_flights and len(outbound_flights) > 0:
                    first_leg = outbound_flights[0]
                    last_leg = outbound_flights[-1]
                    
                    # Try multiple possible keys for departure/arrival times
                    outbound_dep_time = (
                        first_leg.get("departure_airport", {}).get("time") or 
                        first_leg.get("departure_time") or 
                        "TBD"
                    )
                    outbound_arr_time = (
                        last_leg.get("arrival_airport", {}).get("time") or 
                        last_leg.get("arrival_time") or 
                        "TBD"
                    )
                
                # Get airline info
                airline_name = "Various Airlines"
                if outbound_flights and len(outbound_flights) > 0:
                    airline_name = outbound_flights[0].get("airline", "Various Airlines")
                
                # Get price
                price = flight.get("price")
                if price is None:
                    continue  # Skip flights without price
                
                results.append({
                    "outbound_date": search_date,
                    "return_date": search_return,
                    "price": price,
                    "duration": flight.get("total_duration", 0),
                    "airline": airline_name,
                    "outbound_departure_time": outbound_dep_time,
                    "outbound_arrival_time": outbound_arr_time,
                    "return_departure_time": return_dep_time,
                    "return_arrival_time": return_arr_time,
                    "layovers": len(outbound_flights) - 1 if outbound_flights else 0,
                    "booking_link": f"https://www.google.com/travel/flights?q={origin}+to+{destination}+on+{search_date}"
                })
        
        print(f"Total flights found: {len(results)}")  # Debug
        return results
    
    def sort_flights_by_value(self, flight_results):
        """Sort by best value with fallback to all flights"""
        if not flight_results:
            return []
        
        # Remove any flights without prices
        valid_flights = [f for f in flight_results if f.get("price") is not None]
        
        if not valid_flights:
            return []
        
        def flight_score(flight):
            price = flight.get("price", 999999)
            out_dep = self.parse_time(flight.get("outbound_departure_time", "12:00"))
            ret_dep = self.parse_time(flight.get("return_departure_time", "12:00"))
            
            # Normalize scores
            avg_price = sum(f.get("price", 0) for f in valid_flights) / len(valid_flights)
            price_score = price / max(avg_price, 1)
            
            # Combined score: 50% price, 25% early departure, 25% late return
            return (price_score * 0.5) + (out_dep / 24 * 0.25) + (abs(-ret_dep) / 24 * 0.25)
        
        # Sort all flights
        sorted_flights = sorted(valid_flights, key=flight_score)
        
        # Try to get best value flights (within 20% of best price)
        if sorted_flights:
            best_price = sorted_flights[0].get("price", 0)
            threshold = best_price * 1.2
            
            best_value = [f for f in sorted_flights if f.get("price", 999999) <= threshold]
            
            # If we get at least 3 good value flights, return those
            if len(best_value) >= 3:
                return best_value[:10]
        
        # Fallback: return all flights sorted by score
        return sorted_flights[:10]
    
    def create_structured_itinerary(self, destination, keywords, budget, duration_days, hotels_data, airbnb_data):
        hotel_info = ""
        if hotels_data and "properties" in hotels_data:
            hotel_info = "\n\nTop Hotels:\n"
            for hotel in hotels_data["properties"][:3]:
                hotel_info += f"- {hotel.get('name', 'N/A')}: £{hotel.get('rate_per_night', {}).get('lowest', 'N/A')}/night\n"
        
        airbnb_info = ""
        if airbnb_data and "properties" in airbnb_data:
            airbnb_info = "\n\nTop Airbnbs:\n"
            for listing in airbnb_data.get("properties", [])[:3]:
                airbnb_info += f"- {listing.get('name', 'N/A')}: £{listing.get('rate', 'N/A')}/night\n"
        
        prompt = f"""Create a {duration_days}-day structured itinerary for {destination}.

Return ONLY valid JSON with this structure:
{{
  "overview": {{
    "destination": "{destination}",
    "best_time_to_visit": "season info",
    "getting_around": "transport tips",
    "money_saving_tips": ["tip1", "tip2", "tip3"]
  }},
  "daily_itinerary": [
    {{
      "day": 1,
      "theme": "Day theme",
      "breakfast": {{
        "restaurant": "Restaurant name",
        "cuisine": "Type",
        "cost": 12,
        "description": "Why recommended",
        "address": "Location"
      }},
      "morning": {{
        "time": "9:30 AM",
        "activity": "Activity",
        "description": "What to do",
        "cost": 15,
        "duration": "2 hours"
      }},
      "lunch": {{
        "restaurant": "Restaurant name",
        "cuisine": "Type",
        "cost": 18,
        "description": "Why recommended",
        "address": "Location"
      }},
      "afternoon": {{
        "time": "2:00 PM",
        "activity": "Activity",
        "description": "What to do",
        "cost": 25,
        "duration": "3 hours"
      }},
      "dinner": {{
        "restaurant": "Restaurant name",
        "cuisine": "Type",
        "cost": 35,
        "description": "Why recommended",
        "address": "Location"
      }},
      "evening": {{
        "time": "8:00 PM",
        "activity": "Activity",
        "description": "What to do",
        "cost": 20,
        "duration": "2 hours"
      }},
      "daily_total": 125
    }}
  ],
  "budget_summary": {{
    "activities": 200,
    "food": 300,
    "transport": 50,
    "accommodation_estimate": 400,
    "total_estimate": 950
  }}
}}

Include breakfast, lunch, dinner for EACH day.
User interests: {', '.join(keywords)}
Budget: £{budget}
{hotel_info}
{airbnb_info}

JSON only, no other text."""

        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=5000,
            messages=[{"role": "user", "content": prompt}]
        )
        
        response_text = message.content[0].text
        
        try:
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()
            
            return json.loads(response_text)
        except Exception as e:
            print(f"JSON parse error: {e}")
            return {
                "overview": {"destination": destination},
                "daily_itinerary": [],
                "budget_summary": {},
                "raw_text": response_text
            }

agent = FlightSearchAgent()

@app.route('/')
def home():
    try:
        return send_from_directory('.', 'index.html')
    except Exception as e:
        return jsonify({"message": "Flight Search AI Agent", "error": str(e)})

@app.route('/itinerary', methods=['POST'])
def create_itinerary():
    data = request.json
    
    destination = data.get('destination')
    keywords = data.get('keywords', [])
    budget = data.get('budget', 1000)
    origin = data.get('origin')
    outbound_date = data.get('outbound_date')
    return_date = data.get('return_date')
    accommodation_type = data.get('accommodation_type', 'hotels')
    
    if not all([destination, origin, outbound_date]):
        return jsonify({"error": "Missing required fields"}), 400
    
    # Calculate duration
    if return_date:
        start = datetime.strptime(outbound_date, "%Y-%m-%d")
        end = datetime.strptime(return_date, "%Y-%m-%d")
        duration_days = (end - start).days
        if duration_days <= 0:
            duration_days = 1
    else:
        duration_days = data.get('duration_days', 5)
        return_date = (datetime.strptime(outbound_date, "%Y-%m-%d") + timedelta(days=duration_days)).strftime("%Y-%m-%d")
    
    # Search flights
    print(f"Searching flights from {origin} to {destination}")
    all_flights = agent.analyze_flexible_dates(origin, destination, outbound_date, return_date, 7)
    best_flights = agent.sort_flights_by_value(all_flights)
    
    print(f"Best flights count: {len(best_flights)}")
    
    # Search accommodation
    hotels_data = None
    airbnb_data = None
    
    if accommodation_type in ['hotels', 'both']:
        hotels_data = agent.search_hotels(destination, outbound_date, return_date)
    
    if accommodation_type in ['airbnb', 'both']:
        airbnb_data = agent.search_airbnb(destination, outbound_date, return_date)
    
    # Calculate budget
    flight_cost = best_flights[0].get('price', 0) if best_flights else 0
    remaining_budget = budget - flight_cost
    
    # Generate itinerary
    itinerary = agent.create_structured_itinerary(destination, keywords, remaining_budget, duration_days, hotels_data, airbnb_data)
    
    # Format accommodation
    hotel_options = []
    if hotels_data and "properties" in hotels_data:
        for hotel in hotels_data.get("properties", [])[:12]:
            hotel_options.append({
                "name": hotel.get("name", "N/A"),
                "price_per_night": hotel.get("rate_per_night", {}).get("lowest", "N/A"),
                "rating": hotel.get("overall_rating", "N/A"),
                "reviews": hotel.get("reviews", 0),
                "link": hotel.get("link", "#"),
                "description": hotel.get("description", "")[:200],
                "image": hotel.get("images", [{}])[0].get("thumbnail") if hotel.get("images") else None,
                "type": "hotel"
            })
    
    airbnb_options = []
    if airbnb_data and "properties" in airbnb_data:
        for listing in airbnb_data.get("properties", [])[:12]:
            airbnb_options.append({
                "name": listing.get("name", "N/A"),
                "price_per_night": listing.get("rate", "N/A"),
                "rating": listing.get("rating", "N/A"),
                "reviews": listing.get("reviews", 0),
                "link": listing.get("link", "#"),
                "description": f"{listing.get('type', 'Property')} - {listing.get('bedrooms', 0)} bed",
                "image": listing.get("images", [{}])[0] if listing.get("images") else None,
                "type": "airbnb"
            })
    
    return jsonify({
        "destination": destination,
        "keywords": keywords,
        "total_budget": budget,
        "trip_duration": duration_days,
        "outbound_date": outbound_date,
        "return_date": return_date,
        "flight_options": best_flights[:8],
        "recommended_flight_cost": flight_cost,
        "hotel_options": hotel_options,
        "airbnb_options": airbnb_options,
        "remaining_budget": remaining_budget,
        "itinerary": itinerary,
        "accommodation_type": accommodation_type
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
