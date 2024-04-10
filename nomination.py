import csv
from datetime import datetime

class Nomination:
    def __init__(self):
        self.csv_file = "nominees.csv"
        self.votes_csv = "votes.csv"

    def nominate_candidate(self, candidate):
        with open(self.csv_file, mode='a', newline='') as file:
            writer = csv.writer(file)
            writer.writerow([candidate.id, candidate.display_name])

    def get_nominations(self):
        nominations = []
        with open(self.csv_file, mode='r') as file:
            reader = csv.reader(file)
            for row in reader:
                nominations.append((row[0], row[1]))
        return nominations

    def clear_nominations(self):
        open(self.csv_file, 'w').close()  # Clear the contents of the CSV file

    def is_candidate_nominated(self, candidate):
        with open(self.csv_file, mode='r') as file:
            reader = csv.reader(file)
            for row in reader:
                if row[0] == str(candidate.id):
                    return True
        return False
    
    def is_nomination_period_open(self):
        return datetime.now().weekday() < 5
    
    def clear_votes(self):
        open(self.votes_csv, 'w').close()

    def record_vote(self, voter, nominee_id):
        rows = []
        voter_id = str(voter.id)
        with open(self.votes_csv, mode='r') as file:
            reader = csv.reader(file)
            for row in reader:
                if row[0] != voter_id:  # Skip rows for this voter
                    rows.append(row)

        # Write the new vote
        with open(self.votes_csv, mode='w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow([voter_id, nominee_id])
            for row in rows:
                writer.writerow(row)

    def get_votes(self):
        votes = {}
        with open(self.votes_csv, mode='r') as file:
            reader = csv.reader(file)
            for row in reader:
                nominee_id = row[1]
                if nominee_id not in votes:
                    votes[nominee_id] = 1
                else:
                    votes[nominee_id] += 1
        return votes