"""English wording of every template (SPEC §6.2), meaning-for-meaning the Korean `text_ko`.

Quadrants keep their English tool names (`top_left`, ...). Numbers and thresholds are the slots of the
Korean text, formatted the same way. Only the wording differs between the two languages: the question,
the image, the gold program and the gold answer are the same. The Korean text stays the default.
"""

ANSWER_FORMAT_EN = ("(Answer with one of the English names: top_left = upper left, top_right = upper right, "
                    "bottom_left = lower left, bottom_right = lower right.)")
EDGE_EN = "have at least one side of their box within 20 px of the image border"

TEXT_EN = {
    "l1_total_count": lambda s: "How many ships are there in this image?",
    "l1_quadrant_count": lambda s: (f"How many ships are in the {s['region']} quadrant of this image "
                                    f"(by ship center)?"),
    "l1_edge_count": lambda s: f"How many ships in this image {EDGE_EN}?",
    "l1_rect_count": lambda s: ("How many ships in this image have their center inside the rectangle with "
                                "x coordinate {0}~{2} px and y coordinate {1}~{3} px?".format(*s["rect"])),
    "l1_scene": lambda s: "Is this image an inshore scene or an offshore scene?",
    "l1_brightness": lambda s: ("What is the mean brightness (0~255) of the whole image?"
                                if s["region"] == "full" else
                                f"What is the mean brightness (0~255) of the {s['region']} quadrant of this image?"),
    "l2_nearest_ratio": lambda s: ("What percentage of the image width is the center-to-center distance "
                                   "between the two closest ships? (to two decimal places)"),
    "l2_longest_length": lambda s: "How many px is the longer side of the longest ship in this image?",
    "l2_count_over_length": lambda s: (f"How many ships in this image have a longer side of "
                                       f"{s['threshold']} px or more?"),
    "l2_longest_neighbor": lambda s: ("What is the center-to-center distance, in px, from the longest ship "
                                      "to the closest other ship?"),
    "l2_longest_shortest_distance": lambda s: ("What is the center-to-center distance, in px, between the "
                                               "longest ship and the shortest ship?"),
    "l3_quadrant_most_ships": lambda s: (f"Which of the four quadrants has the most ships (by ship center)? "
                                         f"{ANSWER_FORMAT_EN}"),
    "l3_empty_quadrants": lambda s: "How many quadrants contain no ship at all (by ship center)?",
    "l3_quadrant_most_long": lambda s: (f"Which quadrant has the most ships with a longer side of "
                                        f"{s['threshold']} px or more (by ship center)? {ANSWER_FORMAT_EN}"),
    "l3_quadrant_brightest": lambda s: f"Which of the four quadrants has the highest mean brightness? {ANSWER_FORMAT_EN}",
    "l3_quadrant_noisiest": lambda s: (f"Which of the four quadrants has the highest background noise value? "
                                       f"{ANSWER_FORMAT_EN}"),
    "l4_scene_branch": lambda s: ("If this image is an inshore scene, answer the center-to-center distance (px) "
                                  "between the two closest ships; if it is an offshore scene, answer the longer "
                                  "side (px) of the longest ship."),
    "l4_count_branch": lambda s: (f"If this image has {s['threshold'] + 1} or more ships, answer the "
                                  f"center-to-center distance (px) between the two closest ships; otherwise "
                                  f"answer the longer side (px) of the longest ship."),
    "l4_quadrant_branch": lambda s: (f"If the {s['region']} quadrant (by ship center) has {s['threshold']} or more "
                                     f"ships, answer the longer side (px) of the longest ship in that quadrant; "
                                     f"otherwise answer the center-to-center distance (px) between the two "
                                     f"closest ships in the whole image."),
    "l4_maxlen_branch": lambda s: (f"If the longer side of the longest ship in this image is {s['threshold']} px "
                                   f"or more, answer the number of ships whose longer side is {s['threshold']} px "
                                   f"or more; otherwise answer the total number of ships."),
    "l4_noise_branch": lambda s: (f"If the background noise value of the whole image is greater than "
                                  f"{s['threshold']}, answer the total number of ships; otherwise answer the "
                                  f"number of ships that {EDGE_EN}."),
    "l5_noisy_quadrant": lambda s: (f"Find the quadrant with the highest background noise value. If that quadrant "
                                    f"(by ship center) has {s['count_threshold']} or more ships, answer the number "
                                    f"of ships in that quadrant with a longer side of {s['threshold']} px or more; "
                                    f"otherwise answer the number of ships in that quadrant."),
    "l5_scene_quadrant": lambda s: (f"How many ships with a longer side of {s['threshold']} px or more are there "
                                    f"in the quadrant with the highest background noise value if this image is an "
                                    f"inshore scene, or in the quadrant with the most ships (by ship center) if it "
                                    f"is an offshore scene?"),
}
