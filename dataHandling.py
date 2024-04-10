import csv

# Write data to CSV
def write_to_csv(data):
    with open('nominees.csv', mode='a', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(data)

# Read data from CSV
def read_from_csv():
    nominees = []
    with open('nominees.csv', mode='r') as file:
        reader = csv.reader(file)
        for row in reader:
            nominees.append(row)
    return nominees

# Example usage
# Writing data to CSV
nominee_data = ['user_id', 'nominee_id']
write_to_csv(nominee_data)

# Reading data from CSV
nominees = read_from_csv()
print(nominees)
