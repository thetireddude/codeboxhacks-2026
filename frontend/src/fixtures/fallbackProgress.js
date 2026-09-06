const skills = {
  adaptability: { points: 120, rating: "FUNCTIONAL" },
  articulation: { points: 140, rating: "STRONG" },
  coherence: { points: 110, rating: "FUNCTIONAL" },
  collaboration: { points: 130, rating: "STRONG" },
  speed: { points: 100, rating: "FUNCTIONAL" },
};

export const fallbackProgress = [
  {
    match_number: 1,
    match_id: "demo-match-001",
    guest_id: "demo-guest",
    scoring_version: "sample-progress-v1",
    total_score: 600,
    skills,
    overview: "Sample coaching appears until your completed match feedback is available.",
    what_went_well: "You made a clear choice and gave your partner something to build on.",
    what_to_improve: "Try naming the relationship sooner so the scene has a shared point of view.",
    rubric_log: { overview: "Sample coaching appears until your completed match feedback is available.", ...skills },
    created_at: "2026-09-01T18:00:00+00:00",
  },
  {
    match_number: 2,
    match_id: "demo-match-002",
    guest_id: "demo-guest",
    scoring_version: "sample-progress-v1",
    total_score: 735,
    skills: {
      ...skills,
      adaptability: { points: 155, rating: "STRONG" },
      speed: { points: 135, rating: "STRONG" },
    },
    overview: "Sample trend: your quick pivots are becoming a reliable strength.",
    what_went_well: "You accepted the turn quickly and expanded the shared idea.",
    what_to_improve: "Keep each response connected to the previous offer before adding a new detail.",
    rubric_log: {
      overview: "Sample trend: your quick pivots are becoming a reliable strength.",
      adaptability: { points: 155, rating: "STRONG" },
      articulation: { points: 140, rating: "STRONG" },
      coherence: { points: 110, rating: "FUNCTIONAL" },
      collaboration: { points: 130, rating: "STRONG" },
      speed: { points: 135, rating: "STRONG" },
    },
    created_at: "2026-09-02T18:00:00+00:00",
  },
];

export const fallbackProgressSummary = {
  status: "sample",
  tips: [
    { label: "SAMPLE AI OVERVIEW", text: "Your live coaching will appear here after completed matches are saved." },
    { label: "KEEP BUILDING", text: "Make a clear offer, then give your partner room to add to it." },
    { label: "NEXT MATCH", text: "Practice connecting each new detail to the idea already on stage." },
  ],
};
