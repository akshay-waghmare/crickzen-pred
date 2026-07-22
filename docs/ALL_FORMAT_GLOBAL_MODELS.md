# CrickZen Global Men/Women Model Fallback

CrickZen resolves models in this order: a valid league-specific artifact, then the combined gender-aware T20 model for T20, or the combined gender-aware ODI model for ODI. Both combined models use `gender_female` (`male = 0`, `female = 1`) and are trained from `t20s_json/` and `odis_json/`.

Preferred artifacts are `models/t20_all_v2` with `data/t20_all_feature_store_v2`, and `models/odi_all_v2` with `data/odi_all_feature_store_v2`. During the v2 rebuild, v1 is accepted only as a compatibility fallback. The legacy `odi_mc_v1` placeholder is never selected as the full ML fallback.

The resolver preserves the league code for logging, adds `model_source=combined_gender_aware_fallback`, removes ODI `mc_only`, and selects the matching feature store. This prevents a women's match from silently using a men's-only fallback.
