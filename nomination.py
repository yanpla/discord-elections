class Nomination:
    def __init__(self):
        self.nominations = []

    def nominate_candidate(self, candidate):
        self.nominations.append(candidate)

    def get_nominations(self):
        return self.nominations

    def clear_nominations(self):
        self.nominations = []

    def is_candidate_nominated(self, candidate):
        return candidate in self.nominations
