import gymnasium as gym
import numpy as np
from gymnasium import spaces


class RealEstateInvestmentEnv(gym.Env):
    """
    Environnement RL pour la sélection de portefeuille immobilier.
    
    Fix: reset_index() systématique + action clipping pour éviter
    l'erreur "None of [Index([X])] are in the [index]"
    """

    def __init__(self, df, user_profile, max_steps=5):
        super().__init__()

        # ✅ FIX CRITIQUE: reset_index pour garantir indices 0..N-1
        self.df = df.reset_index(drop=True)
        self.user_profile = user_profile

        self.n_assets = len(self.df)
        self.max_steps = max_steps

        # Action = choisir UN bien parmi N
        self.action_space = spaces.Discrete(self.n_assets)

        self.feature_cols = [
            "roi_norm", "risk_score", "user_match_score",
            "price_per_m2", "quality_bonus", "projected_roi",
            "surface_m2", "price_value"
        ]

        # Vérifier que les colonnes existent
        self.feature_cols = [c for c in self.feature_cols if c in self.df.columns]

        self.observation_space = spaces.Box(
            low=-10, high=10,
            shape=(len(self.feature_cols),),
            dtype=np.float32
        )

        self.current_step = 0
        self.selected_indices = []
        self._current_obs_idx = 0

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        self.current_step = 0
        self.selected_indices = []
        self._current_obs_idx = 0
        obs = self._get_obs(0)
        return obs, {}

    def _get_obs(self, idx):
        # ✅ Clamp idx dans les bornes valides
        idx = int(np.clip(idx, 0, self.n_assets - 1))
        row = self.df.iloc[idx][self.feature_cols].values.astype(np.float32)
        row = np.nan_to_num(row, nan=0.0, posinf=1.0, neginf=-1.0)
        std = np.std(row) + 1e-8
        return (row - np.mean(row)) / std

    def step(self, action):
        # ✅ FIX: clamp action dans les bornes
        idx = int(np.clip(action, 0, self.n_assets - 1))

        if idx not in self.selected_indices:
            self.selected_indices.append(idx)

        selected_df = self.df.iloc[self.selected_indices]

        avg_roi = selected_df["projected_roi"].mean() if "projected_roi" in selected_df else 0.06
        avg_risk = selected_df["risk_score"].mean() if "risk_score" in selected_df else 0.3

        budget = self.user_profile.get("budget", 450000)
        total_price = selected_df["price_value"].sum()
        budget_penalty = max(0, total_price / (budget * 1.2) - 1)

        # Diversification bonus: pénaliser si on sélectionne la même ville 2x
        if "city" in selected_df.columns:
            n_unique_cities = selected_df["city"].nunique()
            diversity_bonus = 0.05 * n_unique_cities
        else:
            diversity_bonus = 0.0

        reward = (
            0.55 * avg_roi
            - 0.20 * avg_risk
            - 0.15 * budget_penalty
            + 0.10 * diversity_bonus
        )

        self.current_step += 1
        terminated = self.current_step >= self.max_steps

        # Observation: prochain bien aléatoire
        next_idx = np.random.randint(0, self.n_assets)
        obs = self._get_obs(next_idx)

        return obs, float(reward), terminated, False, {}