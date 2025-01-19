import random
import sys
import os

# -------------------------------------------------------------------
# GLOBALS & DATA
# -------------------------------------------------------------------

# We'll store any "action messages" that result from the player's
# last action (like building, recruiting, quest results, etc.).
last_action_messages = []

last_quest_data = {
    "quest_name": None,
    "difficulty": None,
    "hero_class": None,
}

"""
SLAY THE HYDRA - A Text-Based Kingdom Builder
"""

# Turn/Day count
turn_count = 1

# Game-long stats for summary at the end
class Player_Stats():
    def __init__(self):
        self.gold_spent = 0
        self.food_eaten = 0
        self.arcane_made = 0
        self.quests_succeeded = 0
        self.quests_failed = 0
        self.xp_gained = 0
        self.random_events_held = 0
        self.hydras_slain = 0
        self.debug_used = 0
        self.turn_count = 1

Stats = Player_Stats()

# Base & daily quest limit
base_quests_per_day = 2
quests_per_day = base_quests_per_day
quests_today = 0

# Resources: stored in a dictionary
resources = {
    "Gold": 150,
    "Food": 50,
    "Arcane": 0,  # Arcane Knowledge
}

# Buildings
buildings = {
    "Town Center": 1,  # starts at level 1
    "Farm": 0,
    "Arcane Tower": 0,
    "Barracks": 0,
    "Trading Hall": 0,
    "Blacksmith": 0,
    "Temple": 0,  # New building for worshipping a chosen deity (initially level 0)
}

# Heroes
heroes = {
    "Knight": {
        "level": 1,
        "xp": 0,
        "skills": {
            "Iron Defense": 0,
            "Swordsmanship": 0,
            "Call to Arms": 0,
        }
    },
    "Mage": {
        "level": 0,
        "xp": 0,
        "skills": {
            "Elemental Blast": 0,
            "Mana Efficiency": 0,
            "Arcane Overload": 0,
        }
    },
    "Rogue": {
        "level": 0,
        "xp": 0,
        "skills": {
            "Backstab": 0,
            "Pickpocket": 0,
            "Shadow Cloak": 0,
        }
    },
}

# Hydra progress
hydra_progress = {
    "located": False,   
    "access": False,    
    "gear": False,      
    "fight_unlocked": False
}

# Hydra stats
HYDRA_HP = 1000
HYDRA_DAMAGE = 75

recent_events = []
RECENT_EVENTS_MAX = 3

# -------------------------------------------------------------------
# GOD / GODDESS SYSTEM
# -------------------------------------------------------------------
"""
We define 4 possible deities. Each one has:
- 'key': an internal identifier
- 'base_name': e.g. "God of the Feast" (we'll coin-flip to 'Goddess' at runtime)
- 'bonus_info': short description of the deity's perks
- 'penalty_info': short description of the deity's downside
- (Optional) If you want to store separate logic per deity, you can do so.
We'll keep it simple for the skeleton code: 
They activate once the Temple is built (Temple >= 1).
"""

GODS = [
    {
        "key": "feast",
        "base_name": "God of the Feast",
        "bonus_info": "+1 quest/day, faster hero XP",
        "penalty_info": "Heroes consume 50% more Food daily",
    },
    {
        "key": "harvest",
        "base_name": "God of the Harvest",
        "bonus_info": "+50% Farm production",
        "penalty_info": "No major downside (for now)",
    },
    {
        "key": "hunt",
        "base_name": "God of the Hunt",
        "bonus_info": "Special hunting quest for extra Food & XP",
        "penalty_info": "Could add some mild penalty if desired",
    },
    {
        "key": "tides",
        "base_name": "God of the Tides",
        "bonus_info": "Special seafaring quest (Gold/Arcane gain)",
        "penalty_info": "No direct penalty for now",
    },
]

# Which deity the player is currently pledged to
current_god = None  # Will be set to one of GODS[] after day 25

def randomize_god_titles():
    """
    At the start of the game, flip a coin for each god entry
    to see if we rename "God" -> "Goddess".
    """
    for god in GODS:
        # 50/50 chance
        if random.choice([True, False]):
            # Replace "God of" with "Goddess of"
            god["base_name"] = god["base_name"].replace("God", "Goddess")

def choose_god():
    """
    Called on day 25 (or manually if the player skipped once).
    Lets the player pick from the 4 gods, sets `current_god`.
    """
    global current_god
    reset_messages()

    # If already have a god, do nothing
    if current_god is not None:
        add_message("You already follow a deity.")
        return

    print("A divine presence beckons! It's Day 25!")
    print("Choose your patron deity from among these four:\n")

    for i, deity in enumerate(GODS, 1):
        print(f"({i}) {deity['base_name']}")
        print(f"    Bonus: {deity['bonus_info']}")
        print(f"    Penalty: {deity['penalty_info']}\n")

    print("(q) Decline all (you can choose later via the menu)")

    choice = input("Enter your choice: ").lower()
    if choice == 'q':
        add_message("You declined to choose a deity at this time.")
        return

    try:
        idx = int(choice) - 1
        if 0 <= idx < len(GODS):
            current_god = GODS[idx]
            add_message(f"You have pledged to the {current_god['base_name']}.")
            add_message("Build a Temple (Temple Lv 1) to unlock their blessing!")
        else:
            add_message("Invalid selection.")
    except ValueError:
        add_message("Invalid input, no deity chosen.")


def apply_god_bonuses():
    """
    Called during end_turn() after resource consumption.
    If we have a `current_god` and Temple >= 1, apply that god's daily effects:
    - Could adjust quests_per_day, resource production, etc.
    """
    global quests_per_day

    # Default daily quest limit
    quests_per_day = base_quests_per_day

    if current_god is None:
        return  # No deity chosen, so no bonus

    if buildings["Temple"] < 1:
        return  # Temple not built => no effect

    god_key = current_god["key"]

    # 1) God(dess) of the Feast => +1 quests/day
    if god_key == "feast":
        quests_per_day += 1

    # 2) God(dess) of the Harvest => +50% Farm production
    # (Handled in the actual farm production logic in end_turn, see below.)
    # 3) God(dess) of the Hunt => special quest (god_special_quest), no daily numeric bonus needed
    # 4) God(dess) of the Tides => also special quest, no daily numeric bonus needed

# -------------------------------------------------------------------
# CONFIG
# -------------------------------------------------------------------
BUILDING_INFO = {
    "Town Center": {
        "max_level": 3,
        "upgrade_costs": [(0, 0, 0), (100, 50, 10), (300, 100, 25)],
    },
    "Farm": {
        "max_level": 3,
        "upgrade_costs": [(50, 0, 0), (150, 0, 0), (300, 0, 0)],
        "food_production": [0, 3, 6, 10],
    },
    "Arcane Tower": {
        "max_level": 3,
        "upgrade_costs": [(75, 10, 0), (200, 20, 0), (400, 50, 0)],
        "arcane_production": [0, 1, 3, 7],
    },
    "Barracks": {
        "max_level": 3,
        "upgrade_costs": [(100, 20, 0), (250, 50, 0), (500, 80, 0)],
    },
    "Trading Hall": {
        "max_level": 3,
        "upgrade_costs": [(100, 0, 0), (300, 0, 0), (600, 0, 0)],
        "gold_production": [0, 5, 15, 50],
    },
    "Blacksmith": {
        "max_level": 3,
        "upgrade_costs": [(80, 20, 0), (200, 50, 10), (500, 100, 25)],
    },
    "Temple": {
        # Allows receiving a chosen god's bonus once built
        "max_level": 1,
        "upgrade_costs": [(200, 50, 10)],  # cost to build it to Lv1
    },
}

HERO_XP_TABLE = [10, 20, 40, 70, 110]
HERO_MAX_LEVEL = len(HERO_XP_TABLE)

# -------------------------------------------------------------------
# UTILITY & DISPLAY
# -------------------------------------------------------------------
def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def get_hero_combat_power(hero_class):
    h = heroes[hero_class]
    base_power = h["level"] * 10
    skill_bonus = sum(h["skills"].values()) * 3
    return base_power + skill_bonus

def get_hero_level(hero_class):
    return heroes[hero_class]["level"]

def make_multi_column_status():
    left_lines = []
    left_lines.append(f"Day {turn_count} | Quests Used: {quests_today}/{quests_per_day}")
    left_lines.append("-"*35)
    left_lines.append("RESOURCES:")
    left_lines.append(f"  Gold:   {resources['Gold']}")
    left_lines.append(f"  Food:   {resources['Food']}")
    left_lines.append(f"  Arcane: {resources['Arcane']}")
    left_lines.append("")
    left_lines.append("BUILDINGS:")
    for bld, lvl in buildings.items():
        if bld == "Town Center" or lvl > 0:
            left_lines.append(f"  {bld}: Lv {lvl}")

    right_lines = []
    right_lines.append("HEROES:")
    for hclass, data in heroes.items():
        if data["level"] > 0:
            cpower = get_hero_combat_power(hclass)
            right_lines.append(
                f"  {hclass}: Lv {data['level']}, XP {data['xp']} (Pow {cpower})"
            )
    right_lines.append("")
    right_lines.append("HYDRA PROGRESS:")
    right_lines.append(f"  Located?  {hydra_progress['located']}")
    right_lines.append(f"  Access?   {hydra_progress['access']}")
    right_lines.append(f"  Gear?     {hydra_progress['gear']}")
    right_lines.append(f"  Fight?    {hydra_progress['fight_unlocked']}")

    # Show current deity status
    right_lines.append("")
    if current_god:
        right_lines.append(f"Patron: {current_god['base_name']}")
        if buildings["Temple"] >= 1:
            right_lines.append("  Temple built => Blessings active!")
        else:
            right_lines.append("  Temple NOT built => No blessing yet")

    max_height = max(len(left_lines), len(right_lines))
    combined_lines = []
    for i in range(max_height):
        left_text = left_lines[i] if i < len(left_lines) else ""
        right_text = right_lines[i] if i < len(right_lines) else ""
        combined_lines.append(f"{left_text:<35}  |  {right_text}")

    return "\n".join(combined_lines)

def show_status_and_messages():
    clear_screen()
    status_text = make_multi_column_status()
    print(status_text)
    print("\n" + "="*72 + "\n")
    if last_action_messages:
        print("MESSAGES:")
        for msg in last_action_messages:
            print(f" - {msg}")
        print("")
    print("="*72)

def add_message(msg):
    last_action_messages.append(msg)

def reset_messages():
    last_action_messages.clear()

# -------------------------------------------------------------------
# RANDOM EVENTS
# -------------------------------------------------------------------
def wandering_merchant():
    print("Random Event: Wandering Merchant arrives!")
    print("\n(1) Sell 10 Food for 30 Gold")
    print("(2) Sell 5 Food for 12 Gold")
    print("(3) Trade 5 Arcane for 40 Gold (if you have 5 Arcane)")
    print("(4) Decline the merchant's offer")
    print(f"\n You have {resources['Food']} Food, {resources['Arcane']} Arcane, and {resources['Gold']} Gold.")
    choice = None
    while choice not in ["1","2","3","4"]:
        choice = input("Enter choice: ").lower()

        if choice == '1':
            if resources["Food"] >= 10:
                resources["Food"] -= 10
                resources["Gold"] += 30
                add_message("You sold 10 Food for 30 Gold.")
            else:
                add_message("Not enough Food!")
        elif choice == '2':
            if resources["Food"] >= 5:
                resources["Food"] -= 5
                resources["Gold"] += 12
                add_message("You sold 5 Food for 12 Gold.")
            else:
                add_message("Not enough Food!")
        elif choice == '3':
            if resources["Arcane"] >= 5:
                resources["Arcane"] -= 5
                resources["Gold"] += 40
                add_message("You traded 5 Arcane for 40 Gold.")
            else:
                add_message("Not enough Arcane!")
        elif choice == '4':
            add_message("You declined the merchant's offer.")
            return

def wayward_adventurer():
    add_message("Random Event: Wayward Adventurer!")
    if heroes["Knight"]["level"] >= 2:
        heroes["Knight"]["xp"] += 2
        Stats.xp_gained += 2
        add_message("Your Knight duels the adventurer and gains +2 XP!")
    else:
        add_message("The adventurer finds no worthy opponent and leaves.")

def investor_visit():
    add_message("Random Event: Investor Visit!")
    resources["Gold"] += 100
    add_message("An investor funds your treasury with 100 Gold!")

def event_farm_bumper_crop():
    add_message("Random Event: Bumper Crop at the Farm!")
    food_gain = random.randint(10, 20) + turn_count * 2
    resources["Food"] += food_gain
    add_message(f"Your farms produced an extra {food_gain} Food!")

def event_arcane_experiment():
    add_message("Random Event: Arcane Experiment!")
    if random.randint(1, 100) <= 70:
        arcane_gain = random.randint(5, 15) + turn_count
        resources["Arcane"] += arcane_gain
        Stats.arcane_made += arcane_gain
        add_message(f"Successful experiment! Gained {arcane_gain} Arcane Knowledge.")
    else:
        lost_food = 5
        if resources["Food"] >= lost_food:
            resources["Food"] -= lost_food
            add_message("An experiment backfired, destroying 5 Food!")
        else:
            add_message("A failed experiment caused minor damage to the food stores (but they were almost empty).")

def event_local_festival():
    add_message("Random Event: Local Festival!")
    gold_gain = 5 + turn_count
    food_gain = 5 + turn_count
    resources["Gold"] += gold_gain
    resources["Food"] += food_gain
    add_message(f"The festival brings {gold_gain} Gold and {food_gain} Food!")

def event_royal_inspector():
    add_message("Random Event: Royal Inspector Visits!")
    inspection_target = random.choice(list(buildings.keys()))
    if buildings[inspection_target] < 2:
        gold_loss = 10 + turn_count
        resources["Gold"] -= gold_loss
        add_message(f"The inspector fined you {gold_loss} Gold for an underwhelming {inspection_target}!")
    else:
        gold_gain = 20 + turn_count
        resources["Gold"] += gold_gain
        add_message(f"The inspector was impressed by your kingdom's development! You gained {gold_gain} Gold.")

EVENTS = [
    {
        "name": "wandering_merchant",
        "function": wandering_merchant,
        "base_weight": 10,
        "repeat_block": 1,
        "condition": lambda: True,
        "weight_modifier": lambda: 0
    },
    {
        "name": "wayward_adventurer",
        "function": wayward_adventurer,
        "base_weight": 8,
        "repeat_block": 2,
        "condition": lambda: True,
        "weight_modifier": lambda: 0
    },
    {
        "name": "investor_visit",
        "function": investor_visit,
        "base_weight": 5,
        "repeat_block": 2,
        "condition": lambda: buildings["Trading Hall"] >= 2,
        "weight_modifier": lambda: 0
    },
    {
        "name": "farm_bumper_crop",
        "function": event_farm_bumper_crop,
        "base_weight": 7,
        "repeat_block": 2,
        "condition": lambda: buildings["Farm"] > 0,
        "weight_modifier": lambda: buildings["Farm"] * 3
    },
    {
        "name": "arcane_experiment",
        "function": event_arcane_experiment,
        "base_weight": 6,
        "repeat_block": 1,
        "condition": lambda: buildings["Arcane Tower"] > 0,
        "weight_modifier": lambda: buildings["Arcane Tower"] * 2
    },
    {
        "name": "local_festival",
        "function": event_local_festival,
        "base_weight": 8,
        "repeat_block": 1,
        "condition": lambda: True,
        "weight_modifier": lambda: turn_count // 5
    },
    {
        "name": "royal_inspector",
        "function": event_royal_inspector,
        "base_weight": 3,
        "repeat_block": 2,
        "condition": lambda: True,
        "weight_modifier": lambda: 0
    },
]

# CITIZEN REQUESTS ---------------
def check_citizen_requests():
    roll = random.randint(1, 100)
    if roll > 40:
        return  # no request today
    
    is_Surplus_Food = check_if_surplus_food()


    possible_requests = []
    for req in CITIZEN_REQUESTS:
        # Condition check
        if not req["condition"]():
            continue  # Skip if condition is false

        # Calculate final weight
        final_weight = req["base_weight"] + req["weight_modifier"]()
        if final_weight <= 0:
            continue  # Skip if weight is zero or less

        # Add to possible requests
        possible_requests.append((req, final_weight))

    if not possible_requests:
        return  # No eligible events
    # % chance

    # Example condition: If you have a large surplus of Food (15x daily usage),
    # and Trading Hall >= 1, farmers want to sell extra food.

def check_if_surplus_food():
    total_hero_levels = sum(h["level"] for h in heroes.values())
    daily_food_need = total_hero_levels * 5
    if daily_food_need <= 0:
        return  # no heroes, no request

    # e.g., if you have at least 10x the daily requirement:
    surplus_threshold = daily_food_need * 10
    surplus = resources["Food"] - surplus_threshold
    sell_surplus_offer = int(surplus/5)
    if sell_surplus_offer >= 10 and buildings["Trading Hall"] >= 1:
        return True
    else:
        return False

def request_surplus_food():
    total_hero_levels = sum(h["level"] for h in heroes.values())
    daily_food_need = total_hero_levels * 5
    if daily_food_need <= 0:
        return  # no heroes, no request

    # e.g., if you have at least 15x the daily requirement:
    surplus_threshold = daily_food_need * 10
    surplus = resources["Food"] - surplus_threshold
    sell_surplus_offer = int(surplus/5)
    if resources["Food"] >= surplus_threshold and buildings["Trading Hall"] >= 1 and sell_surplus_offer >= 10:
        # Show a mini choice
        reset_messages()
        print("Citizen Request: Farmers want permission to sell surplus Food at the Trading Hall.")
        print(f"\nThey propose selling {sell_surplus_offer} surplus Food for {sell_surplus_offer * 10} Gold.")
        print(" (1) Approve the sale")
        print(" (2) Deny the request")
        choice = input("Enter choice: ").lower()
        if choice == '1':
            if resources["Food"] >= sell_surplus_offer:
                resources["Food"] -= sell_surplus_offer
                resources["Gold"] += sell_surplus_offer * 10
                add_message(f"You approved the sale. -{sell_surplus_offer} Food, +{sell_surplus_offer * 10} Gold.")
            else:
                add_message(f"You don't actually have {sell_surplus_offer} extra Food. Request fails. To be honest you shouldn't even be able to see this message- if you're reading this, something broke.")
        else:
            add_message("You denied their request.")

def request_arts_district():
    requested_gold = 250 #TODO: Make this dynamic?
    purpose = ["fingerpainting supplies (paint)","fingerpainting supplies (fingers)", "canvases", "marble", "instruments", "ink"]
    reset_messages()
    print("Citizen Request: The Arts Guild requests Gold to furnish a new studio in the Arts District.")
    print(f"\nThey are asking for {requested_gold} Gold for {random.choice(purpose)}.")
    print(" (1) Fund the request")
    print(" (2) Deny the request")
    choice = input("Enter choice: ").lower()
    if choice == '1':
        if resources["Gold"] >= requested_gold:
            resources["Gold"] -= requested_gold
            Stats.gold_spent += requested_gold
            add_message(f"You approved the donation. -{requested_gold} Gold.")
        else:
            add_message(f"You don't actually have {requested_gold} gold. You failed to donate and some child gives up on the arts because of it.")
    else:
        add_message("You denied their request. Enjoy keeping your gold, you greedy tyrant.")    

# Various data storage things for conditions of requests:
is_Surplus_Food = False
hydra_Slain = False



CITIZEN_REQUESTS = [
    {
        "name": "surplus_food",
        "function": request_surplus_food,
        "base_weight": 10,         # Higher = more likely
        "condition": lambda: is_Surplus_Food and buildings["Trading Hall"] >= 1,
        "weight_modifier": lambda: 0  # No dynamic changes
    },
    {
        "name": "arts_district",
        "function": request_arts_district,
        "base_weight": 10,
        "condition": lambda: buildings["Town Center"] >= 2, # Requires Lv2+ Town Center
        "weight_modifier": lambda: 0
    },
]
# -------------------------------------------------------------------
# CORE GAME FUNCTIONS
# -------------------------------------------------------------------
def end_turn():
    global quests_today
    reset_messages()

    # Resource production
    f_level = buildings["Farm"]
    farm_output = 0
    if f_level > 0:
        # If current_god = "harvest" and Temple is built => +50% farm
        if current_god and current_god["key"] == "harvest" and buildings["Temple"] >= 1:
            farm_output = int(BUILDING_INFO["Farm"]["food_production"][f_level] * 1.5)
        else:
            farm_output = BUILDING_INFO["Farm"]["food_production"][f_level]
        resources["Food"] += farm_output

    t_level = buildings["Arcane Tower"]
    if t_level > 0:
        arcane_gain = BUILDING_INFO["Arcane Tower"]["arcane_production"][t_level]
        resources["Arcane"] += arcane_gain
        Stats.arcane_made += arcane_gain

    h_level = buildings["Trading Hall"]
    if h_level > 0:
        gold_gain = BUILDING_INFO["Trading Hall"]["gold_production"][h_level]
        resources["Gold"] += gold_gain

    # Daily food consumption
    total_hero_levels = sum(h["level"] for h in heroes.values())
    base_food_ate = total_hero_levels * 5
    # If "feast" god with Temple => +50% consumption
    if current_god and current_god["key"] == "feast" and buildings["Temple"] >= 1:
        base_food_ate = int(base_food_ate * 1.5)

    # Add small random variation
    variation = int(base_food_ate * random.uniform(-0.05, 0.05))
    food_ate = base_food_ate + variation

    if resources["Food"] < food_ate:
        resources["Food"] = 0
        add_message("You ran out of food to feed your Heroes! They lose some XP from hunger.")
        for hclass, data in heroes.items():
            if data["level"] > 0:
                heroes[hclass]["xp"] = max(0, heroes[hclass]["xp"] - 1)
    else:
        resources["Food"] -= food_ate
        Stats.food_eaten += food_ate
        add_message(f"Your Heroes ate {food_ate} food.")
        if farm_output > 0:
            add_message(f"Your Farms produced {farm_output} Food today.")

    # Quests reset
    quests_today = 0

    # After resource consumption, apply daily god-based changes
    apply_god_bonuses()

    # Then do random events
    day_transition()


def build_or_upgrade():
    reset_messages()
    add_message("You chose: Build/Upgrade a structure")
    options = [
        ("1", "Farm"),
        ("2", "Arcane Tower"),
        ("3", "Barracks"),
        ("4", "Trading Hall"),
        ("5", "Blacksmith"),
        ("6", "Town Center"),
        ("7", "Temple"),  # new building
    ]
    print("\nWhich building to construct or upgrade?")
    for code, bld in options:
        lvl = buildings[bld]
        max_lvl = BUILDING_INFO[bld]["max_level"]
        if lvl < max_lvl:
            gold, food, arcane = BUILDING_INFO[bld]["upgrade_costs"][lvl]
            if (resources["Gold"] >= gold and resources["Food"] >= food and resources["Arcane"] >= arcane):
                print(f"({code}) {bld} (Lv {lvl}) - Cost: {gold}G, {food}F, {arcane}A")
            else:
                print(f"({code}) //{bld} (Lv {lvl}) - Cost: {gold}G, {food}F, {arcane}A")
        else:
            print(f"({code}) {bld} (Max Level Reached)")

    choice = input("Enter choice (1-7) or 'q' to cancel: ").lower()
    if choice == 'q':
        add_message("Cancelled building/upgrade.")
        return

    mapping = {o[0]: o[1] for o in options}
    bld_name = mapping.get(choice)
    if not bld_name:
        add_message("Invalid building choice.")
        return

    lvl = buildings[bld_name]
    max_lvl = BUILDING_INFO[bld_name]["max_level"]
    if lvl >= max_lvl:
        add_message(f"{bld_name} is already at max level.")
        return

    gold_cost, food_cost, arcane_cost = BUILDING_INFO[bld_name]["upgrade_costs"][lvl]
    if (resources["Gold"] >= gold_cost and
        resources["Food"] >= food_cost and
        resources["Arcane"] >= arcane_cost):
        resources["Gold"] -= gold_cost
        Stats.gold_spent += gold_cost
        resources["Food"] -= food_cost
        resources["Arcane"] -= arcane_cost
        buildings[bld_name] += 1
        add_message(f"{bld_name} upgraded to Level {buildings[bld_name]}!")
    else:
        add_message("Not enough resources to upgrade!")
        add_message(f"Required: {gold_cost}G, {food_cost}F, {arcane_cost}A.")
        add_message(f"Available: {resources['Gold']}G, {resources['Food']}F, {resources['Arcane']}A.")

def recruit_or_train_hero():
    reset_messages()
    add_message("You chose: Recruit/Train a hero")
    current_heroes = sum(1 for hero in heroes if heroes[hero]["level"] > 0)
    max_heroes = buildings["Town Center"]

    print("\nWhich hero to recruit or train?")
    hero_list = ["Knight", "Mage", "Rogue"]
    for i, hclass in enumerate(hero_list, start=1):
        lvl = heroes[hclass]["level"]
        if lvl == 0:
            print(f"({i}) Recruit {hclass} (50G, 10F)")
        else:
            if lvl < HERO_MAX_LEVEL:
                needed_xp = HERO_XP_TABLE[lvl - 1] - heroes[hclass]["xp"]
                print(f"({i}) Upgrade {hclass} to Lv {lvl+1} (Needs {needed_xp} more XP)")
            else:
                print(f"({i}) {hclass} is at MAX Level ({HERO_MAX_LEVEL})")
    print("(q) Cancel")

    choice = input("Enter choice: ").lower()
    if choice == 'q':
        add_message("Cancelled hero recruitment/training.")
        return

    hero_map = {'1': "Knight", '2': "Mage", '3': "Rogue"}
    hero_class = hero_map.get(choice)
    if not hero_class:
        add_message("Invalid hero choice.")
        return

    if heroes[hero_class]["level"] == 0:
        # Recruit
        if hero_class in ["Knight", "Rogue"] and buildings["Barracks"] < 1:
            add_message("Requires at least 1 Barracks to recruit Knight/Rogue.")
            return
        if hero_class == "Mage" and buildings["Arcane Tower"] < 1:
            add_message("Requires at least 1 Arcane Tower to recruit Mage.")
            return
        if current_heroes >= max_heroes:
            add_message("Cannot recruit more heroes. Upgrade Town Center for more slots.")
            return

        cost_g = 50
        cost_f = 10
        if resources["Gold"] >= cost_g and resources["Food"] >= cost_f:
            resources["Gold"] -= cost_g
            Stats.gold_spent += cost_g
            resources["Food"] -= cost_f
            heroes[hero_class]["level"] = 1
            add_message(f"Recruited a Level 1 {hero_class}!")
        else:
            add_message("Not enough resources to recruit!")
    else:
        # Upgrade
        lvl = heroes[hero_class]["level"]
        if lvl >= HERO_MAX_LEVEL:
            add_message(f"{hero_class} is already max level.")
            return
        needed_xp = HERO_XP_TABLE[lvl - 1]
        current_xp = heroes[hero_class]["xp"]
        if current_xp >= needed_xp:
            heroes[hero_class]["xp"] -= needed_xp
            heroes[hero_class]["level"] += 1
            new_lvl = heroes[hero_class]["level"]
            add_message(f"{hero_class} advanced to Level {new_lvl}!")
            upgrade_hero_skill(hero_class)
        else:
            shortage = needed_xp - current_xp
            add_message(f"Not enough XP to upgrade {hero_class}. Need {shortage} more XP.")

def upgrade_hero_skill(hero_class):
    add_message(f"Choose a skill to improve for {hero_class}")
    skill_dict = heroes[hero_class]["skills"]
    skill_names = list(skill_dict.keys())
    print("\nWhich skill to upgrade?")
    for i, skill in enumerate(skill_names, 1):
        print(f"({i}) {skill} (Rank {skill_dict[skill]})")
    print("(q) Cancel")

    choice = input("Enter choice: ").lower()
    if choice == 'q':
        add_message("Cancelled skill upgrade.")
        return

    try:
        idx = int(choice) - 1
        if 0 <= idx < len(skill_names):
            selected_skill = skill_names[idx]
            skill_dict[selected_skill] += 1
            add_message(f"{hero_class}'s {selected_skill} is now Rank {skill_dict[selected_skill]}!")
        else:
            add_message("Invalid skill choice.")
    except ValueError:
        add_message("Invalid input for skill choice.")


# QUESTS -----------------------------------------------------------------
def can_gather_resources():
    return True

def can_scout_hydra_location():
    if hydra_progress["located"]:
        return False
    return any(hero["level"] >= 2 for hero in heroes.values())

def can_build_hydra_access():
    return hydra_progress["located"] and not hydra_progress["access"]

def can_craft_hydra_slaying_gear():
    if hydra_progress["gear"]:
        return False
    return buildings["Blacksmith"] >= 2

def on_success_gather_resources(hero_class):
    lvl = get_hero_level(hero_class)
    gold_gain = random.randint(lvl * 10, lvl * 10 + 20)
    food_gain = random.randint(lvl * 5, lvl * 10)
    xp_gain = 2

    # If "feast" is active with Temple => maybe +1 XP
    if current_god and current_god["key"] == "feast" and buildings["Temple"] >= 1:
        xp_gain += 1

    resources["Gold"] += gold_gain
    resources["Food"] += food_gain
    heroes[hero_class]["xp"] += xp_gain
    Stats.xp_gained += xp_gain

    add_message(f"Gained {gold_gain} Gold, {food_gain} Food, and {xp_gain} XP for {hero_class}.")

def on_success_scout_hydra_location(hero_class):
    hydra_progress["located"] = True
    xp_gain = 5
    # Minor synergy for "feast" again
    if current_god and current_god["key"] == "feast" and buildings["Temple"] >= 1:
        xp_gain += 1

    heroes[hero_class]["xp"] += xp_gain
    Stats.xp_gained += xp_gain
    add_message(f"Hydra's lair discovered! +{xp_gain} XP")

def on_success_build_hydra_access(hero_class):
    hydra_progress["access"] = True
    xp_gain = 6
    if current_god and current_god["key"] == "feast" and buildings["Temple"] >= 1:
        xp_gain += 1

    heroes[hero_class]["xp"] += xp_gain
    Stats.xp_gained += xp_gain
    add_message(f"Route to Hydra established! +{xp_gain} XP")

def on_success_craft_hydra_slaying_gear(hero_class):
    hydra_progress["gear"] = True
    xp_gain = 7
    if current_god and current_god["key"] == "feast" and buildings["Temple"] >= 1:
        xp_gain += 1

    heroes[hero_class]["xp"] += xp_gain
    Stats.xp_gained += xp_gain
    add_message(f"Dragonsteel gear forged! +{xp_gain} XP")

# Generic "pray at temple" quest
def can_pray_at_temple():
    return (current_god is not None and buildings["Temple"] >= 1)

def on_success_pray_at_temple(hero_class):
    xp_gain = 2
    if current_god and current_god["key"] == "feast":
        xp_gain += 2
    elif current_god and current_god["key"] == "harvest":
        bonus_food = random.randint(5,15)
        resources["Food"] += bonus_food
        add_message(f"The {current_god['base_name']} blesses your supplies with +{bonus_food} Food!")
    # For "hunt" or "tides" you can do different bonuses
    heroes[hero_class]["xp"] += xp_gain
    Stats.xp_gained += xp_gain
    add_message(f"You prayed at the Temple. +{xp_gain} XP to {hero_class}.")

# A "god_special_quest" that changes effect based on which god is active
def can_god_special_quest():
    return (current_god is not None and buildings["Temple"] >= 1)

def on_success_god_special_quest(hero_class):
    god_key = current_god["key"] if current_god else None
    xp_gain = 4

    if god_key == "feast":
        # Some "Holy Feast" quest
        extra_food = random.randint(10, 20)
        resources["Food"] += extra_food
        xp_gain += 2
        add_message(f"You held a grand feast! +{extra_food} Food, +{xp_gain} XP.")
    elif god_key == "harvest":
        gold_gain = 20
        resources["Gold"] += gold_gain
        add_message(f"Your bountiful harvest was sold for +{gold_gain} Gold!")
        xp_gain += 1
    elif god_key == "hunt":
        hunted_food = random.randint(15, 25)
        resources["Food"] += hunted_food
        xp_gain += 2
        add_message(f"A successful hunt! +{hunted_food} Food, +{xp_gain} XP.")
    elif god_key == "tides":
        gold_gain = random.randint(20,40)
        arcane_gain = random.randint(1,4)
        resources["Gold"] += gold_gain
        resources["Arcane"] += arcane_gain
        add_message(f"A prosperous voyage! +{gold_gain} Gold, +{arcane_gain} Arcane, +{xp_gain} XP.")

    heroes[hero_class]["xp"] += xp_gain
    Stats.xp_gained += xp_gain


QUESTS = {
    "gather_resources": {
        "name": "Gather Resources",
        "difficulty": 50,
        "enabled": can_gather_resources,
        "on_success": on_success_gather_resources
    },
    "scout_hydra_location": {
        "name": "Scout Hydra Location",
        "difficulty": 40,
        "enabled": can_scout_hydra_location,
        "on_success": on_success_scout_hydra_location
    },
    "build_hydra_access": {
        "name": "Build Hydra Access Route",
        "difficulty": 30,
        "enabled": can_build_hydra_access,
        "on_success": on_success_build_hydra_access
    },
    "craft_hydra_slaying_gear": {
        "name": "Craft Hydra-Slaying Gear",
        "difficulty": 20,
        "enabled": can_craft_hydra_slaying_gear,
        "on_success": on_success_craft_hydra_slaying_gear
    },

    "pray_at_temple": {
        "name": "Pray at the Temple",
        "difficulty": 10,
        "enabled": can_pray_at_temple,
        "on_success": on_success_pray_at_temple
    },
    "god_special_quest": {
        "name": "God's Special Quest",
        "difficulty": 40,
        "enabled": can_god_special_quest,
        "on_success": on_success_god_special_quest
    },
}

def send_quest(repeat, quest_key=None, hero_class=None):
    global quests_per_day, quests_today
    reset_messages()

    if quests_today >= quests_per_day:
        add_message("Heroes are tired for today. Wait until tomorrow (End Day).")
        return

    if repeat:
        if quest_key not in QUESTS:
            add_message("That quest doesn't exist.")
            return
        run_quest(quest_key, hero_class)
    else:
        add_message("You chose: Send heroes on a quest")

        available_quests = [k for k, q in QUESTS.items() if q["enabled"]()]

        if not available_quests:
            add_message("No quests are currently available.")
            return

        print("\nAvailable Quests:")
        for i, k in enumerate(available_quests, 1):
            print(f"({i}) {QUESTS[k]['name']}")
        print("(q) Cancel")

        choice = input("Pick a quest: ").lower()
        if choice == 'q':
            add_message("Cancelled sending on a quest.")
            return

        try:
            q_idx = int(choice) - 1
            if q_idx < 0 or q_idx >= len(available_quests):
                add_message("Invalid quest.")
                return
            chosen_key = available_quests[q_idx]
            run_quest(chosen_key, hero_class)
        except ValueError:
            add_message("Invalid input for quest choice.")

def run_quest(quest_key, hero_class=None):
    global quests_today
    if quest_key not in QUESTS:
        add_message("Invalid quest key.")
        return

    qdata = QUESTS[quest_key]
    if not qdata["enabled"]():
        add_message("This quest is unavailable right now.")
        return

    quest_name = qdata["name"]
    difficulty = qdata["difficulty"]

    active_heroes = [h for h,d in heroes.items() if d["level"] > 0]
    if not active_heroes:
        add_message("No heroes available. Recruit someone first.")
        return

    if hero_class is None:
        if len(active_heroes) > 1:
            print(f"\nWhich hero to send on '{quest_name}'?")
            for i, h in enumerate(active_heroes, 1):
                print(f"({i}) {h} (Lv {heroes[h]['level']}, XP {heroes[h]['xp']})")
            print("(q) Cancel quest")
            c = input("Pick a hero: ").lower()
            if c == 'q':
                add_message("Cancelled quest.")
                return
            try:
                h_idx = int(c) - 1
                if h_idx < 0 or h_idx >= len(active_heroes):
                    add_message("Invalid hero choice.")
                    return
                hero_class = active_heroes[h_idx]
            except ValueError:
                add_message("Invalid input for hero choice.")
                return
        else:
            hero_class = active_heroes[0]

    last_quest_data["quest_name"] = quest_name
    last_quest_data["difficulty"] = difficulty
    last_quest_data["hero_class"] = hero_class

    hero_power = get_hero_combat_power(hero_class)
    success_chance = difficulty + hero_power
    if success_chance > 95:
        success_chance = 95

    roll = random.randint(1,100)
    if roll <= success_chance:
        add_message(f"Success on '{quest_name}'! (roll {roll} <= {success_chance})")
        qdata["on_success"](hero_class)
        Stats.quests_succeeded += 1
    else:
        add_message(f"Failure on '{quest_name}' (roll {roll} > {success_chance}). +1 XP to {hero_class}.")
        heroes[hero_class]["xp"] += 1
        Stats.quests_failed += 1
        Stats.xp_gained += 1

    quests_today += 1

    if hydra_progress["located"] and hydra_progress["access"] and hydra_progress["gear"]:
        hydra_progress["fight_unlocked"] = True
        add_message("All prerequisites met! Final battle unlocked.")

def attempt_final_battle():
    reset_messages()
    add_message("You chose: Attempt final Hydra battle")
    if not hydra_progress["fight_unlocked"]:
        add_message("You haven't completed all Hydra prerequisites!")
        return

    total_power = sum(get_hero_combat_power(h) for h in heroes if heroes[h]["level"] > 0)
    if total_power == 0:
        add_message("No heroes available to fight!")
        return

    add_message(f"Your team's total combat power is {total_power}. Hydra HP: {HYDRA_HP}.")
    hydra_hp = HYDRA_HP
    your_team_hp = total_power * 2

    round_num = 0
    while hydra_hp > 0 and your_team_hp > 0:
        round_num += 1
        dmg_to_hydra = int(random.uniform(total_power*0.8, total_power*1.2))
        dmg_from_hydra = int(random.uniform(HYDRA_DAMAGE*0.8, HYDRA_DAMAGE*1.2))

        hydra_hp -= dmg_to_hydra
        your_team_hp -= dmg_from_hydra

        add_message(f"Round {round_num}: You deal {dmg_to_hydra}, Hydra deals {dmg_from_hydra}")
        if hydra_hp <= 0:
            add_message("Hydra is slain! Victory!")
            Stats.hydras_slain += 1
            victory()
            return
        elif your_team_hp <= 0:
            add_message("Your heroes have been defeated and the Hydra flees. Rebuild and try again.")
            hydra_progress['located'] = False
            return

def victory():
    add_message("Congratulations! The Hydra is slain, your kingdom is saved!")
    add_message(Stats.__dict__)

# -------------------------------------------------------------------
# DAY TRANSITION & RANDOM EVENT HOOK
# -------------------------------------------------------------------
def random_events():
    global recent_events
    base_chance = 15 + (buildings["Town Center"] * 5)
    roll = random.randint(1,100)
    if roll > base_chance:
        add_message("Nothing eventful happened.")
        return False

    possible = []
    for evt in EVENTS:
        if not evt["condition"]():
            continue
        block_size = evt["repeat_block"]
        forbidden_slice = recent_events[-block_size:]
        if evt["name"] in forbidden_slice:
            continue
        final_weight = evt["base_weight"] + evt["weight_modifier"]()
        if final_weight <= 0:
            continue
        possible.append((evt, final_weight))

    if not possible:
        return False

    total_weight = sum(w for (_,w) in possible)
    r = random.uniform(0, total_weight)
    cumulative = 0
    chosen_event = None
    for (evt, weight) in possible:
        cumulative += weight
        if r <= cumulative:
            chosen_event = evt
            break

    if not chosen_event:
        return False

    chosen_event["function"]()
    recent_events.append(chosen_event["name"])
    if len(recent_events) > RECENT_EVENTS_MAX:
        recent_events.pop(0)

    Stats.random_events_held += 1
    return True

def day_transition():
    global turn_count
    clear_screen()
    add_message(f"At the end of Day {turn_count - 1}...")

    event_happened = random_events()
    if not event_happened:
        check_citizen_requests()

    total_char = 72 - int(len(f" END OF DAY {turn_count}: "))
    half_char = int(total_char/2)
    print("\n" + "="*half_char + f" END OF DAY {turn_count} " + "="*half_char + "\n")
    if last_action_messages:
        for msg in last_action_messages:
            print(f" - {msg}")
        print("")
    print("="*72)
    input("Press enter to continue...")

    reset_messages()
    turn_count += 1
    Stats.turn_count += 1
    add_message(f"It is now Day {turn_count}.")

    # If day == 25 & no god chosen => prompt
    if turn_count == 25 and current_god is None:
        choose_god()

# -------------------------------------------------------------------
# MAIN MENU
# -------------------------------------------------------------------
def main_menu():
    global turn_count
    while True:
        show_status_and_messages()
        print("\nChoose an action:")
        print("(1) Build or Upgrade a structure")
        print("(2) Recruit or Train a hero")
        if quests_per_day > quests_today:
            print("(3) Send heroes on a quest")
        else:
            print("(3) //Send heroes on a quest")
        if hydra_progress['fight_unlocked']:
            print("(4) Attempt the final Hydra battle (if ready)")
        else:
            #print("(4) //Attempt the final Hydra battle (if ready)")
            pass
        print("(5) End Day (resource collection & random events)")
        if (last_quest_data["quest_name"] and last_quest_data["hero_class"]
            and quests_per_day > quests_today):
            print("(r) Repeat last quest "
                  f"({last_quest_data['quest_name']} with {last_quest_data['hero_class']})")
        else:
            #print("(r) //Repeat last quest (unavailable)")
            pass
        print("(6) View Stats")
        if current_god is None and turn_count > 25:
            print("(g) Choose a God/Goddess")  
        else:
            pass
            #print("(g) //Choose a God (unavailable or already chosen)")
        print("(?) Ask the Oracle for Help")
        print("(q) Quit Game")

        choice = input("Enter choice: ").lower()
        if choice == '1':
            build_or_upgrade()
        elif choice == '2':
            recruit_or_train_hero()
        elif choice == '3':
            send_quest(False, None)
        elif choice == '4':
            attempt_final_battle()
        elif choice == '5':
            end_turn()
        elif choice == '6':
            display_stats()
        elif choice == 'r':
            if (last_quest_data["quest_name"]
                and last_quest_data["hero_class"]
                and quests_per_day > quests_today):
                key = None
                for k,v in QUESTS.items():
                    if v["name"] == last_quest_data["quest_name"]:
                        key = k
                        break
                if key:
                    send_quest(True, key, last_quest_data["hero_class"])
                else:
                    add_message("Could not find last quest key. (Data error?)")
            else:
                add_message("No quest to repeat, or no quests left today.")
        elif choice == 'g':
            # If they haven't chosen a god and we're after day 25, let them pick
            if current_god is None and turn_count > 25:
                choose_god()
            else:
                add_message("You already have a deity or it's not time yet.")
        elif choice == 'q':
            confirm = input("Are you sure you want to quit? (y/n): ").lower()
            if confirm == 'y':
                print("\nThanks for playing!")
                sys.exit(0)
            else:
                continue
        elif "debug" in choice:
            parts = choice.split()
            if len(parts) > 1:
                if parts[1].lower() == "all":
                    for rsc in resources:
                        resources[rsc] += 500
                elif parts[1].lower() == "hydra":
                    for key in hydra_progress.keys():
                        hydra_progress[key] = True
                elif parts[1].lower() in resources:
                    resources[parts[1].lower().capitalize()] += 500
                elif parts[1].lower() == "xp":
                    for h in heroes:
                        heroes[h]["xp"] += 50
                elif parts[1].lower() == "day":
                    turn_count = int(parts[2])
                add_message(f"Performed debug: {choice}")
                Stats.debug_used += 1
                add_message(f"Debug used count: {Stats.debug_used}")
        elif choice == '?':
            help()
        else:
            add_message("Invalid choice. Please try again.")

def help():
    global turn_count
    clear_screen()
    help_options = {
        "Buildings": """ 
Town Center: The heart of your kingdom. Upgrading it increases your capacity for Heroes.
Farm: Produces Food daily.
Arcane Tower: Allows you to train a Mage. Produces Arcane daily.
Barracks: Allows you to train Knights and Rogues.
Trading Hall: Produces a modest amount of Gold daily and enables special events.
Blacksmith: Allows you to craft Hydra-slaying equipment.
Temple: Required to invoke your chosen God's/Goddess's blessing.
""",
        "Heroes": """ 
Heroes are your champions. Only Heroes can be sent on quests and eventually slay the Hydra.
Knight: [Knight info here]
Rogue: [Rogue info here]
Mage: [Mage info here]
""",
        "Resources": """ 
Gold: Used to build and upgrade Buildings, recruit/upgrade Heroes, and special events.
Food: Feeds your Heroes daily. Also used in some building costs and recruitment.
Arcane: Used to build/upgrade the Arcane Tower and in some events.
XP: Accumulates on Heroes. Need enough XP to level them up and learn skills.
""",
        "Quests": """ 
You can attempt a certain number of quests daily (base 2, modified by some gods).
Quests gather resources, progress Hydra objectives, or do special tasks (like praying at the Temple).
""",
        "Events and Requests": """ 
At the end of each day, there is a chance of a random event or citizen request.
These are influenced by your current buildings, resources, or Heroes, and can grant rewards or pose challenges.
""",
        "The Hydra": """ 
To slay the Hydra, you must:
  1) Scout its location,
  2) Build an access route,
  3) Craft slaying gear,
Then attempt the final battle when ready!
""",
        "Gods/Goddesses": """ 
Starting Day 25, you may choose one of four deities (randomly titled God or Goddess).
Build the Temple to activate their unique powers (bonuses & penalties).
You can only follow one at a time.
"""
    }
    if turn_count >= 25:
        god_details = "\n\nAvailable deities:\n"
        for god in GODS:
            god_details += f"- {god['base_name']}: {god['bonus_info']} (Penalty: {god['penalty_info']})\n"
        help_options["Gods/Goddesses"] += god_details

    while True:
        print("HELP MENU:")
        for i,h in enumerate(help_options,1):
            print(f"({i}) {h}")
        print("(q) Back to Main Menu")
        c = input("\nWhat would you like help with? ").lower()
        if c == 'q':
            return
        try:
            idx = int(c)-1
            if idx < 0 or idx >= len(help_options):
                add_message("Invalid help choice.")
                return
            topic = list(help_options.keys())[idx]
            clear_screen()
            print(topic,"-")
            print(help_options[topic])
            print("\n(Press Enter to return to Help Menu)")
            input()
            clear_screen()
        except ValueError:
            add_message("Invalid input for help choice.")
            return

def display_stats():
    add_message(str(Stats.__dict__))

# -------------------------------------------------------------------
# ENTRY POINT
# -------------------------------------------------------------------
if __name__ == "__main__":
    # Randomly rename some "God" -> "Goddess"
    randomize_god_titles()

    clear_screen()
    print("Welcome to SLAY THE HYDRA\n-------------------------\n")
    print("Manage your kingdom, recruit heroes, and complete quests to \n eventually slay the Hydra.")
    print("Now featuring a special surprise at Day 25!\n")
    input("Press Enter to continue...")
    clear_screen()
    main_menu()
