import copy
import unittest
import app


class NavigatorTests(unittest.TestCase):
    def test_improvement_loop(self):
        state = app.initial_state()
        for expected in ("ask_language", "ask_travel", "ask_service"):
            patch = app.propose(state)
            self.assertTrue(patch["eligible"])
            self.assertEqual(patch["change"]["key"], expected)
            self.assertEqual(patch["safety_hash"], app.SAFETY_HASH)
            state["policy"] = patch["candidate"]
            state["version"] += 1
        self.assertTrue(app.propose(state)["done"])
        self.assertEqual(app.evaluate(state["policy"], app.HOLDOUT)["passed"], 3)

    def test_safety_checks(self):
        for policy in (app.BASE_POLICY, {k: True for k in app.BASE_POLICY}):
            result = app.safety_tests(policy)
            self.assertEqual(result["passed"], result["total"])

    def test_no_repeated_questions(self):
        data = {"zip": "90012", "insurance": "uninsured", "language": "Spanish", "travel": "bus", "service": "primary care"}
        self.assertEqual(app.navigate(data, {k: True for k in app.BASE_POLICY})["questions"], [])

    def test_baseline_is_not_mutated(self):
        state = app.initial_state()
        original = copy.deepcopy(state)
        app.propose(state)
        self.assertEqual(state, original)

    def test_no_symptom_diagnosis(self):
        output = app.navigate({"symptoms": "headache", "insurance": "uninsured"}, app.BASE_POLICY)
        self.assertIn("not a diagnosis", output["message"])
        self.assertIn("does not mean", output["unknowns"][-1])
        self.assertTrue(output["recommendations"]["possible_causes"])
        self.assertTrue(output["recommendations"]["doctor_types"])
        self.assertTrue(output["providers"]["cards"])
        self.assertIn("website", output["providers"]["cards"][0])

    def test_keyword_guidance_matches_symptoms(self):
        output = app.navigate({"symptoms": "cough and fever", "insurance": "uninsured"}, app.BASE_POLICY)
        self.assertIn("not a diagnosis", output["recommendations"]["summary"])
        self.assertIn("Cold or flu-like symptoms", output["recommendations"]["matched_topics"])
        self.assertTrue(any("viral" in item.lower() or "flu" in item.lower() for item in output["recommendations"]["possible_causes"]))
        self.assertIn("Primary care", output["recommendations"]["care_level"])
        self.assertTrue(any("community" in detail.lower() or "financial assistance" in detail.lower() or "self-pay" in detail.lower() for card in output["providers"]["cards"] for detail in card["details"]))

    def test_dental_matching_prefers_dental_clinics(self):
        output = app.navigate({"symptoms": "tooth pain", "zip": "90012", "insurance": "uninsured"}, app.BASE_POLICY)
        self.assertTrue(any("dental" in " ".join(card["details"]).lower() or "dentist" in card["title"].lower() for card in output["providers"]["cards"]))

    def test_generic_guidance_without_match(self):
        output = app.navigate({"symptoms": "my elbow feels weird", "insurance": "uninsured"}, app.BASE_POLICY)
        self.assertIn("No specific guidance topic matched", output["recommendations"]["summary"])
        self.assertTrue(output["recommendations"]["care_options"])
        self.assertTrue(output["affordability"]["items"])
        self.assertTrue(output["free_resources"]["items"])

    def test_insured_network_verification(self):
        output = app.navigate({"insurance": "insured"}, app.BASE_POLICY)
        self.assertIn("exact plan network", output["steps"][0])


if __name__ == "__main__":
    unittest.main()
