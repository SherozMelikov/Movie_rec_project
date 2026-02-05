from app.core.model_loader import ModelLoader
from app.services.recommendation_service import RecommendationService

# 1️⃣ Create model loader instance
model_loader = ModelLoader()

# 2️⃣ Create recommendation service
service = RecommendationService(model_loader)

# 3️⃣ Run recomputation synchronously for a user
service._recompute(user_id=1)
