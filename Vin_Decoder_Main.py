# Vehicle Decoder 
# This script decodes vehicle information based on location and input type
import requests

def get_location():
    """Get user's location preference"""
    print("\nSelect your region:")
    print("1. United States (VIN)")
    print("2. United Kingdom (Registration Plate)")
    print("3. European Union (VIN/Registration)")
    
    while True:
        choice = input("\nEnter your choice (1-3): ").strip()
        if choice == "1":
            return "US"
        elif choice == "2":
            return "UK"
        elif choice == "3":
            return "EU"
        else:
            print("Invalid choice. Please enter 1, 2, or 3.")

def decode_us_vin(vin):
    """Decode US VIN using NHTSA API"""
    if len(vin) != 17:    
        print("Please Enter 17 Characters for VIN")
        return None
    
    # API calls
    response = requests.get(f"https://vpic.nhtsa.dot.gov/api/vehicles/decodevin/{vin}?format=json")    
    data = response.json()

    # Dictionary and list approach
    vehicle_specs = {}
    wanted_specs = [
        "Make", "Model", "Model Year", "Engine Model", 
        "Engine Number of Cylinders", "Displacement (L)", 
        "Fuel Type - Primary", "Body Class", "Vehicle Type",
        "Doors", "Seats", "Transmission Style", "Drive Type",
        "Plant City", "Plant Country", "Plant State", 
        "Manufacturer Name", "GVWR", "Curb Weight (lbs)",
        "Wheelbase (inches)", "Series", "Trim", "Engine Power (kW)"
    ]

    # Extract wanted specs from API data
    for item in data["Results"]:
        if item["Variable"] in wanted_specs:
            vehicle_specs[item["Variable"]] = item["Value"]
    
    # Print all specs
    for spec in wanted_specs:
        if spec in vehicle_specs and vehicle_specs[spec]:
            print(f"{spec}: {vehicle_specs[spec]}")
    
    return vehicle_specs

def decode_uk_reg(reg_plate):
    """Decode UK Registration Plate"""
    print(f"UK Registration decoding for: {reg_plate}")
    print("Note: UK API integration coming soon!")
    # TODO: Add UK DVLA API integration
    return None

def decode_eu_vehicle(identifier):
    """Decode EU Vehicle"""
    print(f"EU Vehicle decoding for: {identifier}")
    print("Note: EU API integration coming soon!")
    # TODO: Add EU API integration
    return None

def main():
    """Main function to handle vehicle decoding"""
    location = get_location()
    
    if location == "US":
        vin = input("\nEnter VIN (17 characters): ")
        decode_us_vin(vin)
    elif location == "UK":
        reg_plate = input("\nEnter UK Registration Plate (e.g., AB12 CDE): ")
        decode_uk_reg(reg_plate)
    elif location == "EU":
        identifier = input("\nEnter VIN or Registration: ")
        decode_eu_vehicle(identifier)

# Main execution
if __name__ == "__main__":
    main()
    