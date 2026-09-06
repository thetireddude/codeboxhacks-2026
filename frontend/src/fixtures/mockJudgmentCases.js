const speech = (id, player, text, start, end, accepted = true) => ({ type: "speech", id, player_id: player, text, start_ms: start, end_ms: end, is_final: true, accepted, truncated_by_switch: !accepted, truncated_by_round_end: false });
const swap = (id, from, target, timestamp) => ({ type: "switch", id, from_player_id: from, target_player_id: target, timestamp_ms: timestamp });

export const mockJudgmentCases = [
  { id: "dance", label: "1 · Food-Fueled Flight", summary: "Two Switch recoveries during a desperate orbital-fuel plan.", events: [
    speech("speech_1a", "A", "Since we're out of fuel, we can just use our food to replace it. If it's good enough for me, it's good enough for the ship.", 100, 4200), speech("speech_1b", "B", "I like that idea—", 4500, 5400, false), swap("switch_1", "A", "B", 5400), speech("speech_1c", "B", "I think that would help our lack of kinetic energy and get us into orbit, but what of the consequences?", 5700, 9000), speech("speech_1d", "A", "I don't fear consequences—", 9300, 10400, false), swap("switch_2", "B", "A", 10400), speech("speech_1e", "A", "I eat consequences for breakfast, lunch, and dinner.", 10700, 12900), speech("speech_1f", "B", "This is surely an experience for the resume.", 13200, 15000),
  ] },
  { id: "map", label: "2 · Intern's Map", summary: "Player B turns a vague answer into a specific choice.", events: [
    speech("speech_2a", "A", "Intern, which button lands us safely?", 100, 1500), speech("speech_2b", "B", "The blue one probably does something important—", 1800, 3000, false), swap("switch_2", "A", "B", 3000), speech("speech_2c", "B", "Blue sends an apology; red lands us.", 3300, 6000), speech("speech_2d", "A", "I will press red with my ceremonial elbow.", 6300, 8100), speech("speech_2e", "B", "I will write that in the manual right-side up.", 8400, 9800),
  ] },
  { id: "cheese", label: "3 · Moon Cheese", summary: "Balanced collaboration without a Switch.", events: [
    speech("speech_3a", "A", "The customs officer needs an invitation to land.", 100, 2100), speech("speech_3b", "B", "I forged one in crayon during orientation.", 2400, 4200), speech("speech_3c", "A", "Make it say we deliver emergency moon cheese.", 4500, 6300), speech("speech_3d", "B", "The officer wants a sample before clearing us.", 6600, 8400), speech("speech_3e", "A", "Deploy the cheese cannon and set it to polite.", 8700, 10300),
  ] },
  { id: "comet", label: "4 · Comet Rewrite", summary: "Rapid Switches require Player A to change direction twice.", events: [
    speech("speech_4a", "A", "I will land by following the nearest comet—", 100, 1900, false), swap("switch_4a", "B", "A", 1900), speech("speech_4b", "A", "I will land by becoming friends with the comet—", 2200, 3200, false), swap("switch_4b", "B", "A", 3200), speech("speech_4c", "A", "The comet is our parking attendant.", 3500, 5900), speech("speech_4d", "B", "Ask it to validate our ticket.", 6200, 7900),
  ] },
  { id: "manual", label: "5 · Manual Meltdown", summary: "A rougher scene for concrete improvement feedback.", events: [
    speech("speech_5a", "A", "The manual says do not panic, so I threw it away.", 100, 1800), speech("speech_5b", "B", "That seems bad.", 2100, 2800), speech("speech_5c", "A", "Panic is impossible without a manual—", 3100, 4100, false), swap("switch_5", "B", "A", 4100), speech("speech_5d", "A", "The manual is in the recycling chute, our escape pod.", 4400, 6500), speech("speech_5e", "B", "I will retrieve it unless you have another plan.", 6800, 8200), speech("speech_5f", "A", "I do not.", 8500, 9000),
  ] },
];
