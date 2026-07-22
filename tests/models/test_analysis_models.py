from src.models.analyzed_candidate import AnalyzedCandidate
from src.models.blogger import BloggerProfile
from src.models.candidate_analysis import CandidateAnalysis
from src.models.ideal_blogger_profile import IdealBloggerProfile


def test_create_ideal_blogger_profile() -> None:
    profile = IdealBloggerProfile(
        niche="beauty",
        target_gender="female",
        target_age_range="18-34",
        min_followers=1000,
        max_followers=50000,
        required_topics=["skincare"],
        excluded_topics=["gambling"],
        preferred_regions=["RU"],
        preferred_languages=["ru"],
        required_brand_style="calm expert",
    )

    assert profile.niche == "beauty"
    assert profile.required_topics == ["skincare"]
    assert profile.required_brand_style == "calm expert"


def test_create_candidate_analysis() -> None:
    analysis = CandidateAnalysis(
        overall_score=0.82,
        niche_match_score=0.9,
        audience_match_score=0.8,
        content_quality_score=0.75,
        brand_safety_score=0.95,
        strengths=["relevant niche"],
        weaknesses=["limited contact info"],
        recommendation="shortlist",
        explanation="Strong topical fit.",
        confidence=0.88,
    )

    assert analysis.overall_score == 0.82
    assert analysis.strengths == ["relevant niche"]
    assert analysis.recommendation == "shortlist"


def test_create_analyzed_candidate() -> None:
    blogger = _blogger_profile()
    analysis = _candidate_analysis()

    candidate = AnalyzedCandidate(blogger=blogger, analysis=analysis)

    assert candidate.blogger.username == "creator"
    assert candidate.analysis.recommendation == "shortlist"


def test_list_default_factory_instances_do_not_share_lists() -> None:
    first_profile = IdealBloggerProfile(niche="beauty")
    second_profile = IdealBloggerProfile(niche="fitness")
    first_profile.required_topics.append("skincare")

    first_analysis = _candidate_analysis()
    second_analysis = _candidate_analysis()
    first_analysis.strengths.append("high engagement")

    assert second_profile.required_topics == []
    assert second_analysis.strengths == []
    assert first_profile.required_topics is not second_profile.required_topics
    assert first_analysis.strengths is not second_analysis.strengths


def test_nested_models_are_preserved() -> None:
    candidate = AnalyzedCandidate(
        blogger=_blogger_profile(),
        analysis=_candidate_analysis(),
    )

    assert isinstance(candidate.blogger, BloggerProfile)
    assert isinstance(candidate.analysis, CandidateAnalysis)
    assert candidate.blogger.profile_url == "https://www.instagram.com/creator/"
    assert candidate.analysis.confidence == 0.88


def _blogger_profile() -> BloggerProfile:
    return BloggerProfile(
        input_url="https://www.instagram.com/creator/",
        profile_url="https://www.instagram.com/creator/",
        username="creator",
        full_name="Creator Name",
        biography="Bio",
        followers_count=10000,
        follows_count=500,
        posts_count=120,
        verified=False,
        private=False,
        business_account=True,
        business_category_name="Creator",
        external_url=None,
        public_email=None,
        public_phone_number=None,
        profile_pic_url=None,
        raw_data={"username": "creator"},
    )


def _candidate_analysis() -> CandidateAnalysis:
    return CandidateAnalysis(
        overall_score=0.82,
        niche_match_score=0.9,
        audience_match_score=0.8,
        content_quality_score=0.75,
        brand_safety_score=0.95,
        recommendation="shortlist",
        explanation="Strong topical fit.",
        confidence=0.88,
    )
