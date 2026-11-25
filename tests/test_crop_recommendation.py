import unittest

from ml.crop_recommendation import predict
from ml.train_crop_recommendation import load_dataset


class CropRecommendationTests(unittest.TestCase):
    def test_dataset_loads_all_expected_features(self):
        from pathlib import Path

        dataset = Path(r"C:\Users\HARSHITA\Downloads\crop_dataset_rag_ready.json")
        features, labels = load_dataset(dataset)
        self.assertEqual(len(features), 2200)
        self.assertEqual(len(labels), 2200)
        self.assertEqual(len(set(labels)), 22)
        self.assertTrue(all(len(row) == 7 for row in features))

    def test_trained_model_returns_prediction(self):
        result = predict({
            "nitrogen": 90,
            "phosphorus": 42,
            "potassium": 43,
            "temperature": 24,
            "humidity": 82,
            "ph": 6.5,
            "rainfall": 200,
        })
        self.assertTrue(result["available"])
        self.assertIn(result["recommended_crop"], result["model"]["type"] and [
            "apple", "banana", "blackgram", "chickpea", "coconut", "coffee",
            "cotton", "grapes", "jute", "kidneybeans", "lentil", "maize",
            "mango", "mothbeans", "mungbean", "muskmelon", "orange", "papaya",
            "pigeonpeas", "pomegranate", "rice", "watermelon",
        ])
        self.assertGreaterEqual(result["confidence"], 0)
        self.assertLessEqual(result["confidence"], 1)


if __name__ == "__main__":
    unittest.main()
