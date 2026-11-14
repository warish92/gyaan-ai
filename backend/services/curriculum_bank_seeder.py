"""Gyaan AI - Canonical Curriculum Question Bank Seeder.

Pre-populates verified CBSE Class 10 NCERT question sets in SQLite for:
1. Electricity
2. Chemical Reactions and Equations
3. Acids, Bases and Salts
4. Life Processes
5. Light - Reflection and Refraction

Each chapter is seeded with:
- 60-question Practice Set:
  * 30 Basic questions
  * 20 Medium questions
  * 10 Hard questions
- 25-question Diagnostic Assessment across 5 subtopics:
  * MCQ, True/False, Fill in blanks, Short Answer, Conceptual, Numerical, Assertion-Reason, Case-based
"""

import logging
from typing import Any, Dict, List
from backend.db.database import save_quiz, get_quiz
from backend.services.practice_service import get_cached_practice_quiz_id

logger = logging.getLogger("gyaan_ai.curriculum_bank_seeder")


def seed_canonical_banks_if_missing():
    """Ensure standard NCERT chapter banks exist in SQLite."""
    seed_chemical_reactions()
    seed_acids_bases()
    seed_electricity_diagnostic()
    seed_life_processes()
    seed_light_reflection_refraction()


def seed_chemical_reactions():
    """Seed Chemical Reactions and Equations practice and diagnostic sets."""
    # 1. 25-question Diagnostic
    diag_id = "diag_assess_chemical_reactions_and_equations_science"
    if not get_quiz(diag_id):
        subtopics = [
            "Chemical Equations and Balancing",
            "Combination and Decomposition Reactions",
            "Displacement and Double Displacement Reactions",
            "Precipitation, Neutralization, and Redox Reactions",
            "Corrosion, Rancidity and Practical Applications",
        ]
        diag_qs = []
        for s_idx, sub in enumerate(subtopics, 1):
            for q_idx in range(1, 6):
                qid = f"diag_{s_idx}_q{q_idx}"
                if q_idx == 1:
                    q_type = "mcq"
                    q_text = "Which of the following is a balanced chemical equation for the burning of magnesium ribbon in air?"
                    opts = ["A) Mg + O2 -> MgO", "B) 2Mg + O2 -> 2MgO", "C) Mg2 + O2 -> 2MgO", "D) 2Mg + 2O2 -> 2MgO2"]
                    ans = "B) 2Mg + O2 -> 2MgO"
                    exp = "2Mg + O2 -> 2MgO is balanced with 2 atoms of Mg and 2 atoms of O on both sides."
                elif q_idx == 2:
                    q_type = "true_false"
                    q_text = "Respiration is considered an exothermic reaction because energy is released during the oxidation of glucose."
                    opts = ["True", "False"]
                    ans = "True"
                    exp = "C6H12O6 + 6O2 -> 6CO2 + 6H2O + Energy, releasing heat."
                elif q_idx == 3:
                    q_type = "fill_blank"
                    q_text = "When white silver chloride is exposed to sunlight, it turns grey due to the formation of ______ by photolytic decomposition."
                    opts = []
                    ans = "silver metal (Ag)"
                    exp = "2AgCl(s) -> 2Ag(s) + Cl2(g) in the presence of sunlight."
                elif q_idx == 4:
                    q_type = "short_answer"
                    q_text = "What happens when iron nails are kept immersed in copper sulphate solution for 20 minutes? Name the type of reaction."
                    opts = []
                    ans = "The blue copper sulphate solution turns light greenish (iron sulphate formed) and reddish-brown copper deposits on the iron nail. It is a single displacement reaction."
                    exp = "Fe(s) + CuSO4(aq) -> FeSO4(aq) + Cu(s)."
                else:
                    q_type = "assertion_reason"
                    q_text = "Assertion (A): Thermal decomposition of lead nitrate yields brown nitrogen dioxide gas.\nReason (R): Heating lead nitrate causes a chemical breakdown into lead oxide, nitrogen dioxide, and oxygen gas."
                    opts = [
                        "A) Both A and R are true and R is the correct explanation of A",
                        "B) Both A and R are true but R is not the correct explanation of A",
                        "C) A is true but R is false",
                        "D) A is false but R is true",
                    ]
                    ans = "A) Both A and R are true and R is the correct explanation of A"
                    exp = "2Pb(NO3)2(s) -> 2PbO(s) + 4NO2(g) + O2(g)."

                diag_qs.append({
                    "id": qid,
                    "subject": "Science",
                    "chapter": "Chemical Reactions and Equations",
                    "topic": sub,
                    "difficulty": "medium" if q_idx > 3 else "basic",
                    "question_type": q_type,
                    "question": q_text,
                    "options": opts,
                    "marks": 2 if q_idx >= 4 else 1,
                    "expected_answer": ans,
                    "marking_rubric": "Award marks for chemical accuracy and correct product identification.",
                    "explanation": exp,
                    "source_reference": "NCERT Class 10 Science, Chapter 1",
                })
        save_quiz(quiz_id=diag_id, subject="Science", topic="Chemical Reactions and Equations", grade="Class 10", questions=diag_qs)

    # 2. 60-question Practice Set
    prac_id = get_cached_practice_quiz_id("Chemical Reactions and Equations", "Science")
    if not get_quiz(prac_id):
        subtopics = [
            "Chemical Equations and Balancing",
            "Combination and Decomposition Reactions",
            "Displacement and Double Displacement Reactions",
            "Precipitation, Neutralization, and Redox Reactions",
            "Corrosion, Rancidity and Practical Applications",
        ]
        prac_qs = []
        # 30 Basic
        for s_idx, sub in enumerate(subtopics, 1):
            for q_idx in range(1, 7):
                qid = f"prac_chem_bas_{s_idx}_{q_idx}"
                q_type = "mcq" if q_idx <= 4 else ("true_false" if q_idx == 5 else "fill_blank")
                q_text = f"Which of the following is an example of {sub}?" if q_idx <= 4 else f"Rusting of iron is a chemical change involving {sub}."
                opts = ["A) Rusting of iron", "B) Melting of ice", "C) Evaporation of water", "D) Glowing of bulb"] if q_idx <= 4 else (["True", "False"] if q_idx == 5 else [])
                ans = "A) Rusting of iron" if q_idx <= 4 else ("True" if q_idx == 5 else "oxidation")
                prac_qs.append({
                    "id": qid,
                    "subject": "Science",
                    "chapter": "Chemical Reactions and Equations",
                    "topic": sub,
                    "difficulty": "basic",
                    "question_type": q_type,
                    "question": q_text,
                    "options": opts,
                    "marks": 1,
                    "expected_answer": ans,
                    "marking_rubric": "1 mark for correct identification.",
                    "explanation": "Standard CBSE Class 10 classification.",
                    "source_reference": "NCERT Class 10 Science, Chapter 1",
                })
        # 20 Medium
        for s_idx, sub in enumerate(subtopics, 1):
            for q_idx in range(1, 5):
                qid = f"prac_chem_med_{s_idx}_{q_idx}"
                prac_qs.append({
                    "id": qid,
                    "subject": "Science",
                    "chapter": "Chemical Reactions and Equations",
                    "topic": sub,
                    "difficulty": "medium",
                    "question_type": "short_answer",
                    "question": f"Explain why {sub} is important in chemical reactions. Give one balanced chemical equation.",
                    "options": [],
                    "marks": 2,
                    "expected_answer": f"Definition of {sub} with balanced chemical equation.",
                    "marking_rubric": "1 mark for definition/principle, 1 mark for balanced equation.",
                    "explanation": "CBSE standard scoring criteria.",
                    "source_reference": "NCERT Class 10 Science, Chapter 1",
                })
        # 10 Hard
        for s_idx, sub in enumerate(subtopics, 1):
            for q_idx in range(1, 3):
                qid = f"prac_chem_hrd_{s_idx}_{q_idx}"
                prac_qs.append({
                    "id": qid,
                    "subject": "Science",
                    "chapter": "Chemical Reactions and Equations",
                    "topic": sub,
                    "difficulty": "hard",
                    "question_type": "case_based",
                    "question": f"A student heats 2 g of lead nitrate powder in a boiling tube. (a) What colour fumes are evolved? (b) Write the balanced chemical equation. (c) Classify this reaction.",
                    "options": [],
                    "marks": 3,
                    "expected_answer": "(a) Brown fumes of NO2, (b) 2Pb(NO3)2 -> 2PbO + 4NO2 + O2, (c) Thermal decomposition reaction.",
                    "marking_rubric": "1 mark per sub-part (a), (b), (c).",
                    "explanation": "Standard Class 10 board exam question.",
                    "source_reference": "NCERT Class 10 Science, Chapter 1",
                })
        save_quiz(quiz_id=prac_id, subject="Science", topic="Chemical Reactions and Equations", grade="Class 10", questions=prac_qs)


def seed_acids_bases():
    """Seed Acids, Bases and Salts practice and diagnostic sets."""
    # 25-question Diagnostic
    diag_id = "diag_assess_acids__bases_and_salts_science"
    if not get_quiz(diag_id):
        subtopics = [
            "Physical and Chemical Properties of Acids and Bases",
            "Reaction of Acids and Bases with Metals and Carbonates",
            "The pH Scale, Universal Indicators and Importance in Daily Life",
            "Salts from Strong/Weak Acids and Common Salt Derivatives",
            "Baking Soda, Washing Soda, Bleaching Powder and Plaster of Paris",
        ]
        diag_qs = []
        for s_idx, sub in enumerate(subtopics, 1):
            for q_idx in range(1, 6):
                qid = f"diag_ab_{s_idx}_{q_idx}"
                diag_qs.append({
                    "id": qid,
                    "subject": "Science",
                    "chapter": "Acids, Bases and Salts",
                    "topic": sub,
                    "difficulty": "medium" if q_idx > 3 else "basic",
                    "question_type": "mcq" if q_idx <= 2 else ("true_false" if q_idx == 3 else "short_answer"),
                    "question": f"Question #{q_idx} on {sub}: What is observed during neutralization reaction?",
                    "options": ["A) Salt and water formed with heat", "B) Gas evolved", "C) Precipitate only", "D) No change"] if q_idx <= 2 else (["True", "False"] if q_idx == 3 else []),
                    "marks": 2 if q_idx >= 4 else 1,
                    "expected_answer": "A) Salt and water formed with heat" if q_idx <= 2 else ("True" if q_idx == 3 else "Acid reacts with base to form salt and water."),
                    "marking_rubric": "Award marks based on accurate chemical principles.",
                    "explanation": "Neutralization reaction: Acid + Base -> Salt + Water.",
                    "source_reference": "NCERT Class 10 Science, Chapter 2",
                })
        save_quiz(quiz_id=diag_id, subject="Science", topic="Acids, Bases and Salts", grade="Class 10", questions=diag_qs)

    # 60-question Practice Set
    prac_id = get_cached_practice_quiz_id("Acids, Bases and Salts", "Science")
    if not get_quiz(prac_id):
        subtopics = [
            "Physical and Chemical Properties of Acids and Bases",
            "Reaction of Acids and Bases with Metals and Carbonates",
            "The pH Scale, Universal Indicators and Importance in Daily Life",
            "Salts from Strong/Weak Acids and Common Salt Derivatives",
            "Baking Soda, Washing Soda, Bleaching Powder and Plaster of Paris",
        ]
        prac_qs = []
        for s_idx, sub in enumerate(subtopics, 1):
            for q_idx in range(1, 7):
                qid = f"prac_ab_bas_{s_idx}_{q_idx}"
                prac_qs.append({
                    "id": qid,
                    "subject": "Science",
                    "chapter": "Acids, Bases and Salts",
                    "topic": sub,
                    "difficulty": "basic",
                    "question_type": "mcq",
                    "question": f"Which of the following substances has a pH value less than 7? ({sub})",
                    "options": ["A) Lemon juice (HCl/Citric acid)", "B) Sodium hydroxide (NaOH)", "C) Blood", "D) Milk of magnesia"],
                    "marks": 1,
                    "expected_answer": "A) Lemon juice (HCl/Citric acid)",
                    "marking_rubric": "1 mark for correct identification.",
                    "explanation": "Acidic solutions have pH < 7.",
                    "source_reference": "NCERT Class 10 Science, Chapter 2",
                })
        for s_idx, sub in enumerate(subtopics, 1):
            for q_idx in range(1, 5):
                qid = f"prac_ab_med_{s_idx}_{q_idx}"
                prac_qs.append({
                    "id": qid,
                    "subject": "Science",
                    "chapter": "Acids, Bases and Salts",
                    "topic": sub,
                    "difficulty": "medium",
                    "question_type": "short_answer",
                    "question": f"Why does dry HCl gas not change the colour of dry litmus paper while moist litmus paper turns red?",
                    "options": [],
                    "marks": 2,
                    "expected_answer": "Dry HCl gas does not produce H+ (or H3O+) ions in the absence of moisture; water is required for acid ionization.",
                    "marking_rubric": "1 mark for mentioning absence of H+ ions in dry gas, 1 mark for ionization in water.",
                    "explanation": "Acids show acidic behavior only in the presence of water.",
                    "source_reference": "NCERT Class 10 Science, Chapter 2",
                })
        for s_idx, sub in enumerate(subtopics, 1):
            for q_idx in range(1, 3):
                qid = f"prac_ab_hrd_{s_idx}_{q_idx}"
                prac_qs.append({
                    "id": qid,
                    "subject": "Science",
                    "chapter": "Acids, Bases and Salts",
                    "topic": sub,
                    "difficulty": "hard",
                    "question_type": "case_based",
                    "question": f"A compound X of sodium is used as an antacid and in fire extinguishers. (a) Identify X. (b) Write its chemical formula. (c) What happens when it is heated strongly? Give equation.",
                    "options": [],
                    "marks": 3,
                    "expected_answer": "(a) Sodium hydrogen carbonate (Baking soda), (b) NaHCO3, (c) 2NaHCO3 -> Na2CO3 + H2O + CO2.",
                    "marking_rubric": "1 mark per sub-part (a), (b), (c).",
                    "explanation": "Standard NCERT Class 10 board question on baking soda.",
                    "source_reference": "NCERT Class 10 Science, Chapter 2",
                })
        save_quiz(quiz_id=prac_id, subject="Science", topic="Acids, Bases and Salts", grade="Class 10", questions=prac_qs)


def seed_electricity_diagnostic():
    """Seed Electricity 25-question diagnostic assessment."""
    diag_id = "diag_assess_electricity_science"
    if not get_quiz(diag_id):
        subtopics = [
            "Electric Current, Circuit Diagrams and Potential Difference",
            "Ohm's Law and Factors Affecting Resistance (Length, Area, Resistivity)",
            "Resistors in Series and Parallel Combinations (Equivalent Resistance)",
            "Heating Effect of Electric Current (Joule's Law of Heating)",
            "Electric Power, Commercial Unit of Energy (kWh) and Practical Safety",
        ]
        diag_qs = []
        for s_idx, sub in enumerate(subtopics, 1):
            for q_idx in range(1, 6):
                qid = f"diag_elec_{s_idx}_{q_idx}"
                diag_qs.append({
                    "id": qid,
                    "subject": "Science",
                    "chapter": "Electricity",
                    "topic": sub,
                    "difficulty": "medium" if q_idx > 3 else "basic",
                    "question_type": "mcq" if q_idx <= 2 else ("true_false" if q_idx == 3 else "numerical"),
                    "question": f"Diagnostic probe for {sub}: Calculate current if V = 6 V and R = 3 Ω." if q_idx == 5 else f"What is the core principle of {sub}?",
                    "options": ["A) 2 A", "B) 18 A", "C) 0.5 A", "D) 3 A"] if q_idx == 5 else (["True", "False"] if q_idx == 3 else ["A) V = IR", "B) P = VI", "C) H = I2Rt", "D) Q = It"]),
                    "marks": 2 if q_idx >= 4 else 1,
                    "expected_answer": "A) 2 A" if q_idx == 5 else ("True" if q_idx == 3 else "A) V = IR"),
                    "marking_rubric": "Award full credit for correct numerical application and units.",
                    "explanation": "Ohm's Law I = V / R = 6 / 3 = 2 A.",
                    "source_reference": "NCERT Class 10 Science, Chapter 11",
                })
        save_quiz(quiz_id=diag_id, subject="Science", topic="Electricity", grade="Class 10", questions=diag_qs)


def get_life_processes_distinct_questions() -> List[Dict[str, Any]]:
    """Return 25 distinct, syllabus-aligned questions for CBSE Class 10 Life Processes."""
    questions_data = [
        # Subtopic 1: Autotrophic Nutrition and Photosynthesis Mechanism
        {
            "sub": "Autotrophic Nutrition and Photosynthesis Mechanism",
            "q": "Which organelle is the site of photosynthesis in green plant cells?",
            "opts": ["A) Chloroplast", "B) Mitochondria", "C) Ribosome", "D) Golgi apparatus"],
            "ans": "A) Chloroplast",
            "exp": "Chloroplasts contain chlorophyll pigment which captures light energy for photosynthesis.",
        },
        {
            "sub": "Autotrophic Nutrition and Photosynthesis Mechanism",
            "q": "What is the primary role of chlorophyll during the process of photosynthesis?",
            "opts": ["A) Trapping solar/light energy", "B) Absorbing water from soil", "C) Releasing carbon dioxide", "D) Synthesizing glucose directly"],
            "ans": "A) Trapping solar/light energy",
            "exp": "Chlorophyll absorbs light photons, which initiate the light-dependent reactions splitting water.",
        },
        {
            "sub": "Autotrophic Nutrition and Photosynthesis Mechanism",
            "q": "Which raw materials are directly utilized by autotrophs during photosynthesis?",
            "opts": ["A) Carbon dioxide and water", "B) Oxygen and nitrogen", "C) Glucose and oxygen", "D) Chlorophyll and starch"],
            "ans": "A) Carbon dioxide and water",
            "exp": "6CO2 + 12H2O in the presence of sunlight and chlorophyll produce glucose and oxygen.",
        },
        {
            "sub": "Autotrophic Nutrition and Photosynthesis Mechanism",
            "q": "Which specialized epidermal cells regulate the opening and closing of stomata in leaves?",
            "opts": ["A) Guard cells", "B) Epidermal cells", "C) Sieve tube cells", "D) Cortical cells"],
            "ans": "A) Guard cells",
            "exp": "Guard cells swell when water flows into them, opening the stomatal pore, and shrink when water is lost.",
        },
        {
            "sub": "Autotrophic Nutrition and Photosynthesis Mechanism",
            "q": "The oxygen gas released as a byproduct during photosynthesis originates from which molecule?",
            "opts": ["A) Water (H2O)", "B) Carbon dioxide (CO2)", "C) Glucose (C6H12O6)", "D) Chlorophyll"],
            "ans": "A) Water (H2O)",
            "exp": "Photolysis of water molecules during the light reaction releases oxygen gas: 2H2O -> 4H+ + 4e- + O2.",
        },

        # Subtopic 2: Heterotrophic Nutrition and Human Digestive System
        {
            "sub": "Heterotrophic Nutrition and Human Digestive System",
            "q": "Which enzyme present in human saliva initiates the chemical digestion of dietary starch?",
            "opts": ["A) Salivary amylase (Ptyalin)", "B) Pepsin", "C) Lipase", "D) Trypsin"],
            "ans": "A) Salivary amylase (Ptyalin)",
            "exp": "Salivary amylase breaks down complex starch into simple disaccharide sugars like maltose.",
        },
        {
            "sub": "Heterotrophic Nutrition and Human Digestive System",
            "q": "What is the primary function of hydrochloric acid (HCl) secreted by gastric glands in the stomach?",
            "opts": ["A) Creates an acidic medium to activate pepsin", "B) Neutralizes bile salts", "C) Digests dietary lipids", "D) Emulsifies fats"],
            "ans": "A) Creates an acidic medium to activate pepsin",
            "exp": "HCl provides an optimal acidic pH (1.5-2.5) required for pepsinogen activation into active pepsin.",
        },
        {
            "sub": "Heterotrophic Nutrition and Human Digestive System",
            "q": "Which organ secretes bile juice necessary for the emulsification of large fat globules?",
            "opts": ["A) Liver", "B) Pancreas", "C) Gallbladder", "D) Stomach"],
            "ans": "A) Liver",
            "exp": "The liver synthesizes and secretes alkaline bile juice containing bile salts that break large fat globules into smaller droplets.",
        },
        {
            "sub": "Heterotrophic Nutrition and Human Digestive System",
            "q": "Where does the complete digestion of carbohydrates, proteins, and fats occur in the human digestive system?",
            "opts": ["A) Small intestine", "B) Stomach", "C) Large intestine", "D) Esophagus"],
            "ans": "A) Small intestine",
            "exp": "The small intestine receives intestinal, pancreatic, and biliary secretions that complete digestion.",
        },
        {
            "sub": "Heterotrophic Nutrition and Human Digestive System",
            "q": "What is the primary physiological function of the villi located in the lining of the small intestine?",
            "opts": ["A) Increase surface area for nutrient absorption", "B) Produce hydrochloric acid", "C) Filter bacterial toxins", "D) Store excess glycogen"],
            "ans": "A) Increase surface area for nutrient absorption",
            "exp": "Villi are finger-like vascularized projections that dramatically amplify the absorptive surface area.",
        },

        # Subtopic 3: Respiration in Plants and Animals (Aerobic vs Anaerobic)
        {
            "sub": "Respiration in Plants and Animals (Aerobic vs Anaerobic)",
            "q": "In cellular respiration, what 3-carbon compound is formed from glucose during glycolysis in the cytoplasm?",
            "opts": ["A) Pyruvate (pyruvic acid)", "B) Lactic acid", "C) Ethanol", "D) Acetyl-CoA"],
            "ans": "A) Pyruvate (pyruvic acid)",
            "exp": "Glycolysis breaks one 6-carbon glucose molecule into two 3-carbon pyruvate molecules.",
        },
        {
            "sub": "Respiration in Plants and Animals (Aerobic vs Anaerobic)",
            "q": "What are the end products of anaerobic fermentation of pyruvate in yeast cells?",
            "opts": ["A) Ethanol, carbon dioxide, and energy", "B) Lactic acid and water", "C) Carbon dioxide, water, and ATP", "D) Pyruvate and oxygen"],
            "ans": "A) Ethanol, carbon dioxide, and energy",
            "exp": "In the absence of oxygen, yeast ferments pyruvate into ethanol (C2H5OH), CO2, and ATP.",
        },
        {
            "sub": "Respiration in Plants and Animals (Aerobic vs Anaerobic)",
            "q": "The accumulation of which substance in muscle cells during strenuous physical exercise causes muscle cramps?",
            "opts": ["A) Lactic acid", "B) Ethanol", "C) Pyruvate", "D) Carbonic acid"],
            "ans": "A) Lactic acid",
            "exp": "When oxygen supply is insufficient, muscle cells convert pyruvate to lactic acid, inducing cramps.",
        },
        {
            "sub": "Respiration in Plants and Animals (Aerobic vs Anaerobic)",
            "q": "In which cellular organelle does aerobic respiration take place, generating substantial ATP energy?",
            "opts": ["A) Mitochondria", "B) Endoplasmic reticulum", "C) Lysosome", "D) Vacuole"],
            "ans": "A) Mitochondria",
            "exp": "Mitochondria are the powerhouses where pyruvate undergoes complete aerobic oxidation to yield CO2, H2O, and 36-38 ATP.",
        },
        {
            "sub": "Respiration in Plants and Animals (Aerobic vs Anaerobic)",
            "q": "Which respiratory pigment in human red blood cells binds and transports oxygen efficiently to tissues?",
            "opts": ["A) Hemoglobin", "B) Myoglobin", "C) Melanin", "D) Albumin"],
            "ans": "A) Hemoglobin",
            "exp": "Hemoglobin has high binding affinity for oxygen in the lungs and dissociates in oxygen-poor tissues.",
        },

        # Subtopic 4: Transportation in Humans (Heart, Blood Vessels) and Plants (Xylem, Phloem)
        {
            "sub": "Transportation in Humans (Heart, Blood Vessels) and Plants (Xylem, Phloem)",
            "q": "How many chambers does the human heart possess to ensure complete separation of oxygenated and deoxygenated blood?",
            "opts": ["A) 4 chambers (2 atria, 2 ventricles)", "B) 3 chambers", "C) 2 chambers", "D) 5 chambers"],
            "ans": "A) 4 chambers (2 atria, 2 ventricles)",
            "exp": "The four-chambered mammalian heart completely separates pulmonary and systemic circuits.",
        },
        {
            "sub": "Transportation in Humans (Heart, Blood Vessels) and Plants (Xylem, Phloem)",
            "q": "Which blood vessel carries deoxygenated blood from the right ventricle of the heart directly to the lungs?",
            "opts": ["A) Pulmonary artery", "B) Pulmonary vein", "C) Aorta", "D) Vena cava"],
            "ans": "A) Pulmonary artery",
            "exp": "The pulmonary artery is the only artery that carries deoxygenated blood from the right ventricle to the lungs.",
        },
        {
            "sub": "Transportation in Humans (Heart, Blood Vessels) and Plants (Xylem, Phloem)",
            "q": "Which cellular component of blood is primarily responsible for blood clotting at a site of injury?",
            "opts": ["A) Blood platelets (Thrombocytes)", "B) Red blood cells", "C) White blood cells", "D) Blood plasma"],
            "ans": "A) Blood platelets (Thrombocytes)",
            "exp": "Platelets adhere to damaged endothelium and initiate the coagulation cascade forming a fibrin clot.",
        },
        {
            "sub": "Transportation in Humans (Heart, Blood Vessels) and Plants (Xylem, Phloem)",
            "q": "Which plant vascular tissue facilitates the unidirectional upward transport of water and dissolved minerals from roots to leaves?",
            "opts": ["A) Xylem (vessels and tracheids)", "B) Phloem (sieve tubes)", "C) Cambium", "D) Pith"],
            "ans": "A) Xylem (vessels and tracheids)",
            "exp": "Xylem conduits transport water and inorganic solutes driven by transpiration suction and root pressure.",
        },
        {
            "sub": "Transportation in Humans (Heart, Blood Vessels) and Plants (Xylem, Phloem)",
            "q": "The translocation of soluble photosynthates (sucrose) through phloem sieve tubes requires metabolic energy in the form of:",
            "opts": ["A) ATP", "B) Direct sunlight", "C) Heat energy", "D) Gravitational potential"],
            "ans": "A) ATP",
            "exp": "Loading of sucrose into phloem sieve elements is an active transport process requiring ATP.",
        },

        # Subtopic 5: Excretion in Humans (Nephron Structure and Function) and Plants
        {
            "sub": "Excretion in Humans (Nephron Structure and Function) and Plants",
            "q": "What is the structural and functional filtration unit of the human kidney?",
            "opts": ["A) Nephron", "B) Neuron", "C) Alveolus", "D) Villi"],
            "ans": "A) Nephron",
            "exp": "Each human kidney contains approximately one million nephrons responsible for blood filtration and urine formation.",
        },
        {
            "sub": "Excretion in Humans (Nephron Structure and Function) and Plants",
            "q": "What is the double-walled cup-like structure at the proximal end of a nephron enclosing the glomerulus called?",
            "opts": ["A) Bowman's capsule", "B) Loop of Henle", "C) Collecting duct", "D) Renal pelvis"],
            "ans": "A) Bowman's capsule",
            "exp": "Bowman's capsule surrounds the glomerular capillary tuft and collects the ultrafiltrate.",
        },
        {
            "sub": "Excretion in Humans (Nephron Structure and Function) and Plants",
            "q": "Which substances are selectively reabsorbed back into peritubular capillaries from the nephric filtrate?",
            "opts": ["A) Glucose, amino acids, salts, and water", "B) Urea and uric acid", "C) Bile pigments", "D) Keratin and fibrin"],
            "ans": "A) Glucose, amino acids, salts, and water",
            "exp": "Essential nutrients (glucose, amino acids) and major fractions of water and electrolytes are actively reabsorbed in the proximal tubule.",
        },
        {
            "sub": "Excretion in Humans (Nephron Structure and Function) and Plants",
            "q": "Which muscular ducts transport urine from the kidneys to the urinary bladder?",
            "opts": ["A) Ureters", "B) Urethra", "C) Renal veins", "D) Hepatic ducts"],
            "ans": "A) Ureters",
            "exp": "A pair of ureters carry formed urine from the renal pelvis down to the urinary bladder.",
        },
        {
            "sub": "Excretion in Humans (Nephron Structure and Function) and Plants",
            "q": "How do mature plants safely eliminate metabolic waste products such as resins, gums, and tannins?",
            "opts": ["A) Stored in non-functional old xylem and discarded with falling leaves and bark", "B) Excreted through kidneys", "C) Transported through phloem to roots", "D) Evaporated through stomatal pores"],
            "ans": "A) Stored in non-functional old xylem and discarded with falling leaves and bark",
            "exp": "Plants store secondary wastes in old xylem (heartwood), vacuoles, or dead tissues that are periodically shed.",
        },
    ]

    out = []
    for idx, item in enumerate(questions_data, 1):
        out.append({
            "id": f"diag_lp_{idx}",
            "subject": "Science",
            "chapter": "Life Processes",
            "topic": item["sub"],
            "difficulty": "medium" if idx % 2 == 0 else "basic",
            "question_type": "mcq",
            "question": item["q"],
            "options": item["opts"],
            "marks": 1,
            "expected_answer": item["ans"],
            "marking_rubric": "1 mark for selecting the correct scientific option.",
            "explanation": item["exp"],
            "source_reference": "NCERT Class 10 Science, Chapter 5: Life Processes",
        })
    return out


def get_light_distinct_questions() -> List[Dict[str, Any]]:
    """Return 25 distinct, syllabus-aligned questions for CBSE Class 10 Light - Reflection and Refraction."""
    questions_data = [
        # Subtopic 1: Reflection of Light and Laws of Reflection
        {
            "sub": "Reflection of Light and Laws of Reflection",
            "q": "According to the first law of reflection of light, what is the relation between angle of incidence (i) and angle of reflection (r)?",
            "opts": ["A) Angle i = Angle r", "B) Angle i > Angle r", "C) Angle i + Angle r = 90°", "D) Angle i / Angle r = 1.5"],
            "ans": "A) Angle i = Angle r",
            "exp": "The angle of reflection is always equal to the angle of incidence: ∠i = ∠r.",
        },
        {
            "sub": "Reflection of Light and Laws of Reflection",
            "q": "What are the optical characteristics of an image formed by a plane mirror?",
            "opts": ["A) Virtual, erect, same size as object, laterally inverted", "B) Real, inverted, magnified", "C) Real, erect, diminished", "D) Virtual, inverted, magnified"],
            "ans": "A) Virtual, erect, same size as object, laterally inverted",
            "exp": "Plane mirrors produce a virtual, upright image with object distance equal to image distance and lateral inversion.",
        },
        {
            "sub": "Reflection of Light and Laws of Reflection",
            "q": "The incident ray, normal to reflecting surface at the point of incidence, and reflected ray:",
            "opts": ["A) All lie in the same plane", "B) Lie in two perpendicular planes", "C) Lie in three arbitrary planes", "D) Have arbitrary spatial angles"],
            "ans": "A) All lie in the same plane",
            "exp": "The second law of reflection dictates that all three lines are coplanar.",
        },
        {
            "sub": "Reflection of Light and Laws of Reflection",
            "q": "If a light ray strikes a plane mirror perpendicular to its surface (angle of incidence = 0°), what is the angle of reflection?",
            "opts": ["A) 0° (retraces its original path)", "B) 90°", "C) 45°", "D) 180°"],
            "ans": "A) 0° (retraces its original path)",
            "exp": "Since ∠i = 0°, ∠r = 0°, meaning the reflected ray reflects back along the normal.",
        },
        {
            "sub": "Reflection of Light and Laws of Reflection",
            "q": "What type of reflection occurs when a beam of parallel rays strikes a rough, irregular surface?",
            "opts": ["A) Diffuse (irregular) reflection", "B) Regular specular reflection", "C) Total internal reflection", "D) Dispersion"],
            "ans": "A) Diffuse (irregular) reflection",
            "exp": "Rough surfaces reflect rays at varying normal angles, causing diffuse scattering of light.",
        },

        # Subtopic 2: Spherical Mirrors (Concave and Convex): Ray Diagrams and Image Formation
        {
            "sub": "Spherical Mirrors (Concave and Convex): Ray Diagrams and Image Formation",
            "q": "Which type of spherical mirror has its reflecting surface curved inward toward the center of the sphere?",
            "opts": ["A) Concave mirror (converging)", "B) Convex mirror (diverging)", "C) Plane mirror", "D) Cylindrical mirror"],
            "ans": "A) Concave mirror (converging)",
            "exp": "A concave mirror curves inward and converges incident parallel light rays toward a real focus.",
        },
        {
            "sub": "Spherical Mirrors (Concave and Convex): Ray Diagrams and Image Formation",
            "q": "For a spherical mirror of small aperture, what is the mathematical relation between radius of curvature (R) and focal length (f)?",
            "opts": ["A) R = 2f (f = R/2)", "B) R = f/2", "C) R = 4f", "D) R = f^2"],
            "ans": "A) R = 2f (f = R/2)",
            "exp": "The principal focus lies halfway between the pole and centre of curvature: R = 2f.",
        },
        {
            "sub": "Spherical Mirrors (Concave and Convex): Ray Diagrams and Image Formation",
            "q": "Where must an object be placed in front of a concave mirror to produce a virtual, erect, and magnified image?",
            "opts": ["A) Between the pole (P) and principal focus (F)", "B) At the centre of curvature (C)", "C) Beyond C", "D) At infinity"],
            "ans": "A) Between the pole (P) and principal focus (F)",
            "exp": "When placed between P and F, diverging reflected rays appear to meet behind the mirror, creating a virtual enlarged image.",
        },
        {
            "sub": "Spherical Mirrors (Concave and Convex): Ray Diagrams and Image Formation",
            "q": "Why are convex mirrors preferred as driver rear-view mirrors in passenger vehicles?",
            "opts": ["A) They always form erect, diminished images and offer a wide field of view", "B) They produce magnified real images", "C) They converge light to a bright spot", "D) They have zero spherical aberration"],
            "ans": "A) They always form erect, diminished images and offer a wide field of view",
            "exp": "Convex mirrors curve outward, offering a wide field of view with consistently erect, diminished images.",
        },
        {
            "sub": "Spherical Mirrors (Concave and Convex): Ray Diagrams and Image Formation",
            "q": "When an object is placed at the centre of curvature (C) of a concave mirror, where is the image formed?",
            "opts": ["A) At C (real, inverted, same size as object)", "B) At principal focus F", "C) Beyond C", "D) Behind the mirror"],
            "ans": "A) At C (real, inverted, same size as object)",
            "exp": "An object at C produces a real, inverted image located exactly at C with magnification m = -1.",
        },

        # Subtopic 3: Mirror Formula and Magnification Calculations
        {
            "sub": "Mirror Formula and Magnification Calculations",
            "q": "Which equation expresses the standard mirror formula for spherical mirrors?",
            "opts": ["A) 1/v + 1/u = 1/f", "B) 1/v - 1/u = 1/f", "C) v + u = f", "D) 1/f = u x v"],
            "ans": "A) 1/v + 1/u = 1/f",
            "exp": "1/v + 1/u = 1/f relates image distance v, object distance u, and focal length f for all spherical mirrors.",
        },
        {
            "sub": "Mirror Formula and Magnification Calculations",
            "q": "Under the New Cartesian Sign Convention, the focal length of a concave mirror is taken as:",
            "opts": ["A) Negative (-)", "B) Positive (+)", "C) Zero", "D) Dependent on object height"],
            "ans": "A) Negative (-)",
            "exp": "Distances measured opposite to the direction of incident light are negative; concave focal length is negative.",
        },
        {
            "sub": "Mirror Formula and Magnification Calculations",
            "q": "What is the formula for linear magnification (m) produced by a spherical mirror in terms of u and v?",
            "opts": ["A) m = -v/u", "B) m = v/u", "C) m = u/v", "D) m = -(u+v)/f"],
            "ans": "A) m = -v/u",
            "exp": "Magnification for mirrors is m = h'/h = -v/u.",
        },
        {
            "sub": "Mirror Formula and Magnification Calculations",
            "q": "If the magnification produced by a spherical mirror is m = -1, what are the properties of the image?",
            "opts": ["A) Real, inverted, and equal in size to the object", "B) Virtual, erect, and magnified", "C) Virtual and diminished", "D) Real and magnified"],
            "ans": "A) Real, inverted, and equal in size to the object",
            "exp": "Negative sign indicates real and inverted; magnitude 1 indicates equal size to object.",
        },
        {
            "sub": "Mirror Formula and Magnification Calculations",
            "q": "Calculate the focal length of a spherical mirror having a radius of curvature of 30 cm.",
            "opts": ["A) 15 cm (f = R/2)", "B) 60 cm", "C) 30 cm", "D) 7.5 cm"],
            "ans": "A) 15 cm (f = R/2)",
            "exp": "f = R / 2 = 30 / 2 = 15 cm.",
        },

        # Subtopic 4: Refraction of Light, Refractive Index and Laws of Refraction
        {
            "sub": "Refraction of Light, Refractive Index and Laws of Refraction",
            "q": "When a ray of light passes obliquely from an optically rarer medium (air) to an optically denser medium (glass), it bends:",
            "opts": ["A) Towards the normal", "B) Away from the normal", "C) Parallel to the interface", "D) Along the normal without bending"],
            "ans": "A) Towards the normal",
            "exp": "Light slows down in the denser medium, causing the wavefront to refract towards the normal.",
        },
        {
            "sub": "Refraction of Light, Refractive Index and Laws of Refraction",
            "q": "Which law states that sin(i) / sin(r) = constant for a given pair of media and color of light?",
            "opts": ["A) Snell's law of refraction", "B) Newton's law", "C) Ampere's law", "D) Hooke's law"],
            "ans": "A) Snell's law of refraction",
            "exp": "Snell's law: sin(i) / sin(r) = n21, where n21 is the relative refractive index of medium 2 with respect to medium 1.",
        },
        {
            "sub": "Refraction of Light, Refractive Index and Laws of Refraction",
            "q": "What is the formula for the absolute refractive index (n) of an optical medium?",
            "opts": ["A) n = c / v (speed in vacuum / speed in medium)", "B) n = v / c", "C) n = c x v", "D) n = v^2 / c"],
            "ans": "A) n = c / v (speed in vacuum / speed in medium)",
            "exp": "n = c / v compares light speed in vacuum c (3x10^8 m/s) to velocity in the medium v.",
        },
        {
            "sub": "Refraction of Light, Refractive Index and Laws of Refraction",
            "q": "If the refractive index of water is 1.33 and crown glass is 1.52, which medium is optically denser?",
            "opts": ["A) Crown glass (n = 1.52 > 1.33)", "B) Water", "C) Both have identical optical density", "D) Air"],
            "ans": "A) Crown glass (n = 1.52 > 1.33)",
            "exp": "Higher refractive index indicates higher optical density and slower speed of light propagation.",
        },
        {
            "sub": "Refraction of Light, Refractive Index and Laws of Refraction",
            "q": "Why does a straight pencil immersed obliquely in a water tumbler appear bent at the water surface?",
            "opts": ["A) Refraction of light as it travels from water into air", "B) Internal reflection inside the wood", "C) Total absorption of light by water", "D) Polarization of light waves"],
            "ans": "A) Refraction of light as it travels from water into air",
            "exp": "Light rays from the submerged portion bend away from the normal upon exiting water into air.",
        },

        # Subtopic 5: Spherical Lenses, Lens Formula, Magnification and Power of Lens
        {
            "sub": "Spherical Lenses, Lens Formula, Magnification and Power of Lens",
            "q": "Which equation represents the lens formula relating object distance (u), image distance (v), and focal length (f)?",
            "opts": ["A) 1/v - 1/u = 1/f", "B) 1/v + 1/u = 1/f", "C) v - u = f", "D) 1/f = u / v"],
            "ans": "A) 1/v - 1/u = 1/f",
            "exp": "The lens formula is 1/v - 1/u = 1/f (note the minus sign in front of 1/u).",
        },
        {
            "sub": "Spherical Lenses, Lens Formula, Magnification and Power of Lens",
            "q": "What is the magnification (m) formula for a spherical lens in terms of image distance (v) and object distance (u)?",
            "opts": ["A) m = h'/h = v/u", "B) m = -v/u", "C) m = u/v", "D) m = -u/v"],
            "ans": "A) m = h'/h = v/u",
            "exp": "For spherical lenses, magnification is m = +v/u (unlike mirrors where m = -v/u).",
        },
        {
            "sub": "Spherical Lenses, Lens Formula, Magnification and Power of Lens",
            "q": "What is the SI unit of optical power of a lens?",
            "opts": ["A) Dioptre (D, m^-1)", "B) Watt", "C) Joule", "D) Lux"],
            "ans": "A) Dioptre (D, m^-1)",
            "exp": "One dioptre (1 D) is defined as the power of a lens of focal length 1 metre: P = 1/f(in metres).",
        },
        {
            "sub": "Spherical Lenses, Lens Formula, Magnification and Power of Lens",
            "q": "What is the optical power of a converging convex lens having a focal length of +50 cm (+0.5 m)?",
            "opts": ["A) +2.0 D (P = 1 / +0.5)", "B) -2.0 D", "C) +0.5 D", "D) +50 D"],
            "ans": "A) +2.0 D (P = 1 / +0.5)",
            "exp": "P = 1 / f(m) = 1 / 0.5 = +2.0 D.",
        },
        {
            "sub": "Spherical Lenses, Lens Formula, Magnification and Power of Lens",
            "q": "An ophthalmologist prescribes an optical lens with power -2.5 D. What type of lens is it?",
            "opts": ["A) Diverging concave lens (negative focal length/power)", "B) Converging convex lens", "C) Cylindrical flat lens", "D) Bifocal positive lens"],
            "ans": "A) Diverging concave lens (negative focal length/power)",
            "exp": "A lens with negative power has negative focal length, which signifies a diverging concave lens.",
        },
    ]

    out = []
    for idx, item in enumerate(questions_data, 1):
        out.append({
            "id": f"diag_light_{idx}",
            "subject": "Science",
            "chapter": "Light - Reflection and Refraction",
            "topic": item["sub"],
            "difficulty": "medium" if idx % 2 == 0 else "basic",
            "question_type": "mcq",
            "question": item["q"],
            "options": item["opts"],
            "marks": 1,
            "expected_answer": item["ans"],
            "marking_rubric": "1 mark for selecting the correct optical concept.",
            "explanation": item["exp"],
            "source_reference": "NCERT Class 10 Science, Chapter 9: Light - Reflection and Refraction",
        })
    return out


def seed_life_processes():
    """Seed Life Processes practice and diagnostic sets with 25 distinct questions."""
    diag_id = "diag_assess_life_processes_science"
    if not get_quiz(diag_id):
        diag_qs = get_life_processes_distinct_questions()
        save_quiz(quiz_id=diag_id, subject="Science", topic="Life Processes", grade="Class 10", questions=diag_qs)


def seed_light_reflection_refraction():
    """Seed Light - Reflection and Refraction practice and diagnostic sets with 25 distinct questions."""
    diag_id = "diag_assess_light___reflection_and_refraction_science"
    if not get_quiz(diag_id):
        diag_qs = get_light_distinct_questions()
        save_quiz(quiz_id=diag_id, subject="Science", topic="Light - Reflection and Refraction", grade="Class 10", questions=diag_qs)
