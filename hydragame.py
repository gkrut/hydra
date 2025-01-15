import random
import sys
import os

# -------------------------------------------------------------------
# GLOBALS & DATA
# -------------------------------------------------------------------

# We'll store any "action messages" that result from the player's
# last action (like building, recruiting, quest results, etc.).
last_action_messages = []

"""
SLAY THE HYDRA - A Text-Based Kingdom Builder
---------------------------------------------

Core Features:
- Manage resources (Gold, Food, Arcane Knowledge).
- Build and upgrade structures for passive income and new options.
- Recruit and train heroes (Knight, Mage, Rogue) with simple skill trees.
- Undertake mini-quests to:
    1. Scout Hydra's Location,
    2. Build Hydra Access Route,
    3. Craft Hydra-Slaying Gear.
- Face random events (e.g., Wandering Merchant, Investor) influenced by your builds.
- Finally, attempt to slay the Hydra in a simple text-based battle!
"""

# Daily quest limit: move things along
quests_per_day = 2
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
RECENT_EVENTS_MAX = 3  # or however many you'd like
# Event dict definied below

# Turn/Day count
turn_count = 1

# -------------------------------------------------------------------
# CONFIG
# -------------------------------------------------------------------
BUILDING_INFO = {
    "Town Center": {
        "max_level": 3,
        "upgrade_costs": [(100, 50, 10), (300, 100, 25)],  # for levels 2, 3
    },
    "Farm": {
        "max_level": 3,
        "upgrade_costs": [(50, 0, 0), (150, 0, 0), (300, 0, 0)],
        "food_production": [0, 3, 6, 10],  # index=level => production
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
}

HERO_MAX_LEVEL = 5
HERO_XP_TABLE = [10, 20, 40, 70, 110]

# -------------------------------------------------------------------
# UTILITY & DISPLAY
# -------------------------------------------------------------------

def clear_screen():
    """
    Clears the console using ANSI escape sequences.
    This should work on most Unix and modern Windows terminals.
    """
    os.system('cls')

def get_hero_combat_power(hero_class):
    """Calculate total 'combat power' for a hero."""
    h = heroes[hero_class]
    base_power = h["level"] * 10
    skill_bonus = sum(h["skills"].values()) * 3
    return base_power + skill_bonus

def get_hero_level(hero_class):
    h = heroes[hero_class]
    level = h["level"]
    return level

def make_multi_column_status():
    """
    Returns a string with a two-column layout for the major sections:
    1) Resources & Buildings
    2) Heroes & Hydra Progress
    You can adjust spacing, widths, or add more columns as desired.
    """
    # Left column: Day, Quests, Resources, Buildings
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

    # Right column: Heroes, Hydra
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

    # Combine the two columns line by line
    # We'll define a max height so we can zip them properly
    max_height = max(len(left_lines), len(right_lines))
    combined_lines = []
    for i in range(max_height):
        left_text = left_lines[i] if i < len(left_lines) else ""
        right_text = right_lines[i] if i < len(right_lines) else ""
        # Format them in columns: adjust spacing as needed
        combined_lines.append(f"{left_text:<35}  |  {right_text}")

    return "\n".join(combined_lines)

def show_status_and_messages():
    """
    Clears the screen, prints the multi-column status,
    then prints any action messages in a separate section below.
    """
    clear_screen()
    status_text = make_multi_column_status()
    print(status_text)
    print("\n" + "="*72 + "\n")
    # Print any messages from last actions
    if last_action_messages:
        print("MESSAGES:")
        for msg in last_action_messages:
            print(f" - {msg}")
        print("")
    print("="*72)

def add_message(msg):
    """
    Helper to append a message to the last_action_messages list.
    """
    last_action_messages.append(msg)

def reset_messages():
    """
    Clear the list of action messages before a new action
    so we only see the *latest* messages after each menu choice.
    """
    last_action_messages.clear()

# -------------------------------------------------------------------
# RANDOM EVENTS
# -------------------------------------------------------------------

def random_events():
    global recent_events
    reset_messages()
    # 1) Check if we pass the base "any event?" chance
    base_chance = 15 + (buildings["Trading Hall"] * 5)
    roll = random.randint(1, 100)
    if roll > base_chance:
        return  # No event this turn

    # 2) Build a Weighted List of possible events
    possible_events = []
    for evt in EVENTS:
        # Condition check
        if not evt["condition"]():
            continue  # Skip if condition is false

        # Check repeat-block
        block_size = evt["repeat_block"]
        forbidden_slice = recent_events[-block_size:]  # Last `block_size` events
        if evt["name"] in forbidden_slice:
            continue  # Skip this event if it was recently triggered

        # Calculate final weight
        final_weight = evt["base_weight"] + evt["weight_modifier"]()
        if final_weight <= 0:
            continue  # Skip if weight is zero or less

        # Add to possible events
        possible_events.append((evt, final_weight))

    if not possible_events:
        return  # No eligible events

    # 3) Weighted random choice
    total_weight = sum(weight for (_, weight) in possible_events)
    r = random.uniform(0, total_weight)
    cumulative = 0
    chosen_event = None
    for (evt, w) in possible_events:
        cumulative += w
        if r <= cumulative:
            chosen_event = evt
            break

    if chosen_event is None:
        return  # Failsafe, should not happen

    # 4) Trigger the chosen event
    chosen_event["function"]()

    # 5) Record the event in recent_events
    recent_events.append(chosen_event["name"])
    if len(recent_events) > RECENT_EVENTS_MAX:
        recent_events.pop(0)  # Keep recent_events list short

def wandering_merchant():
    add_message("Random Event: Wandering Merchant!")
    if resources["Food"] >= 10:
        resources["Food"] -= 10
        resources["Gold"] += 30
        add_message("You sold 10 Food for 30 Gold.")
    else:
        add_message("Not enough Food. The merchant leaves disappointed.")

def wayward_adventurer():
    add_message("Random Event: Wayward Adventurer!")
    if heroes["Knight"]["level"] >= 2:
        heroes["Knight"]["xp"] += 2
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
        add_message(f"Successful experiment! Gained {arcane_gain} Arcane Knowledge.")
    else:
        lost_food = 5
        if resources["Food"] >= lost_food:
            resources["Food"] -= lost_food
            add_message("An experiment backfired, destroying 5 Food!")
        else:
            add_message("A failed experiment caused minor damage to the food stores. Luckily they were empty!")

def event_local_festival():
    add_message("Random Event: Local Festival!")
    gold_gain = 5 + turn_count
    food_gain = 5 + turn_count
    resources["Gold"] += gold_gain
    resources["Food"] += food_gain
    add_message(f"The festival brings {gold_gain} Gold and {food_gain} Food!")

def event_royal_inspector():
    add_message("Random Event: Royal Inspector Visits!")
    if buildings["Town Center"] < 2:
        gold_loss = 10 + turn_count
        resources["Gold"] -= gold_loss
        add_message(f"The inspector fined you {gold_loss} Gold for your underwhelming Town Center!")
    else:
        gold_gain = 20 + turn_count
        resources["Gold"] += gold_gain
        add_message(f"The inspector was impressed! You gained {gold_gain} Gold.")

EVENTS = [
    {
        "name": "wandering_merchant",
        "function": wandering_merchant,
        "base_weight": 10,         # Higher = more likely
        "repeat_block": 1,         # Block this event for 1 round after it occurs
        "condition": lambda: True, # Always eligible
        "weight_modifier": lambda: 0  # No dynamic changes
    },
    {
        "name": "wayward_adventurer",
        "function": wayward_adventurer,
        "base_weight": 8,
        "repeat_block": 2,         # Wait for 2 other events
        "condition": lambda: True, # Always eligible
        "weight_modifier": lambda: 0
    },
    {
        "name": "investor_visit",
        "function": investor_visit,
        "base_weight": 5,
        "repeat_block": 2,  # Happens less often
        "condition": lambda: buildings["Trading Hall"] >= 2,  # Needs Trading Hall Level 2+
        "weight_modifier": lambda: 0  # No scaling
    },
    {
        "name": "farm_bumper_crop",
        "function": event_farm_bumper_crop,
        "base_weight": 7,
        "repeat_block": 2,
        "condition": lambda: buildings["Farm"] > 0,  # Needs at least 1 Farm
        "weight_modifier": lambda: buildings["Farm"] * 3  # Weight scales by Farm level
    },
    {
        "name": "arcane_experiment",
        "function": event_arcane_experiment,
        "base_weight": 6,
        "repeat_block": 1,
        "condition": lambda: buildings["Arcane Tower"] > 0,  # Needs Arcane Tower
        "weight_modifier": lambda: buildings["Arcane Tower"] * 2  # Scales by Tower level
    },
    {
        "name": "local_festival",
        "function": event_local_festival,
        "base_weight": 8,
        "repeat_block": 1,
        "condition": lambda: True,  # Always eligible
        "weight_modifier": lambda: turn_count // 5  # Slightly more likely as time passes
    },
    {
        "name": "royal_inspector",
        "function": event_royal_inspector,
        "base_weight": 3,  # Rare
        "repeat_block": 2,  # Can't happen back-to-back
        "condition": lambda: True,  # Always eligible
        "weight_modifier": lambda: 0  # No scaling
    },
]

# -------------------------------------------------------------------
# CORE GAME FUNCTIONS
# -------------------------------------------------------------------

def end_turn():
    global quests_today
    # Resource production
    f_level = buildings["Farm"]
    if f_level > 0:
        resources["Food"] += BUILDING_INFO["Farm"]["food_production"][f_level]

    t_level = buildings["Arcane Tower"]
    if t_level > 0:
        resources["Arcane"] += BUILDING_INFO["Arcane Tower"]["arcane_production"][t_level]

    h_level = buildings["Trade Hall"]
    if h_level > 0:
        resources["Gold"] += BUILDING_INFO["Trade Hall"]["gold_production"][h_level]

    active_heroes = [h for h, d in heroes.items() if d["level"] > 0]
    for hero in active_heroes:
        

    quests_today = 0

    # Trigger random event
    random_events()

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
    ]
    print("\nWhich building to construct or upgrade?")
    for code, bld in options:
        current_level = buildings[bld]
        if current_level < BUILDING_INFO[bld]["max_level"]:
            gold, food, arcane = BUILDING_INFO[bld]["upgrade_costs"][current_level]
            if (resources["Gold"] >= gold and resources["Food"] >= food and resources["Arcane"] >= arcane):
            	print(f"({code}) {bld} (Lv {current_level}) - Cost: {gold}G, {food}F, {arcane}A")
            else:
            	print(f"({code}) //{bld} (Lv {current_level}) - Cost: {gold}G, {food}F, {arcane}A")
        else:
            print(f"({code}) {bld} (Max Level Reached)")

    choice = input("Enter choice (1-6) or 'q' to cancel: ").lower()
    if choice == 'q':
        add_message("Cancelled building/upgrade.")
        return

    mapping = {o[0]: o[1] for o in options}
    bld_name = mapping.get(choice)
    if not bld_name:
        add_message("Invalid building choice.")
        return

    current_level = buildings[bld_name]
    max_level = BUILDING_INFO[bld_name]["max_level"]
    if current_level >= max_level:
        add_message(f"{bld_name} is already at max level.")
        return

    gold_cost, food_cost, arcane_cost = BUILDING_INFO[bld_name]["upgrade_costs"][current_level]
    if (resources["Gold"] >= gold_cost and
        resources["Food"] >= food_cost and
        resources["Arcane"] >= arcane_cost):
        resources["Gold"] -= gold_cost
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

    # Display possible hero actions
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

    # Check if recruiting or upgrading
    if heroes[hero_class]["level"] == 0:
        # Recruiting new hero
        if hero_class in ["Knight", "Rogue"] and buildings["Barracks"] < 1:
            add_message("Requires at least 1 Barracks to recruit Knight/Rogue.")
            return
        if hero_class == "Mage" and buildings["Arcane Tower"] < 1:
            add_message("Requires at least 1 Arcane Tower to recruit Mage.")
            return
        if current_heroes >= max_heroes:
            add_message("Cannot recruit more heroes. Upgrade Town Center for more slots.")
            return

        recruit_cost_gold = 50
        recruit_cost_food = 10
        if resources["Gold"] >= recruit_cost_gold and resources["Food"] >= recruit_cost_food:
            resources["Gold"] -= recruit_cost_gold
            resources["Food"] -= recruit_cost_food
            heroes[hero_class]["level"] = 1
            add_message(f"Recruited a Level 1 {hero_class}!")
        else:
            add_message("Not enough resources to recruit!")
    else:
        # Upgrading an existing hero
        lvl = heroes[hero_class]["level"]
        if lvl >= HERO_MAX_LEVEL:
            add_message(f"{hero_class} is already at max level.")
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
    # Show skill options
    skill_dict = heroes[hero_class]["skills"]
    add_message(f"Choose a skill to improve for {hero_class}")
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

def send_quest():
    global quests_per_day, quests_today
    reset_messages()
    add_message("You chose: Send heroes on a quest")
    if quests_per_day <= quests_today:
        add_message("Heroes are tired for today. Wait until tomorrow (End Day).")
        return

    quests = [
        "Gather Resources",
        "Scout Hydra Location",
        "Build Hydra Access Route",
        "Craft Hydra-Slaying Gear"
    ]
    quest_difficulties = {
        "Gather Resources": 50,
        "Scout Hydra Location": 40,
        "Build Hydra Access Route": 30,
        "Craft Hydra-Slaying Gear": 20
    }
    print("\nAvailable Quests:")
    for i, q in enumerate(quests, 1):
        print(f"({i}) {q}")
    print("(q) Cancel")

    choice = input("Pick a quest: ").lower()
    if choice == 'q':
        add_message("Cancelled sending on a quest.")
        return

    try:
        q_idx = int(choice) - 1
        if q_idx < 0 or q_idx >= len(quests):
            add_message("Invalid quest.")
            return
        quest_name = quests[q_idx]
        run_quest(quest_name, quest_difficulties[quest_name])
    except ValueError:
        add_message("Invalid input for quest choice.")

def run_quest(quest_name, difficulty):
    global quests_today
    active_heroes = [h for h, d in heroes.items() if d["level"] > 0]
    if not active_heroes:
        add_message("No heroes available. Recruit someone first.")
        return
    if len(active_heroes) > 1:
      print(f"\nWhich hero to send on '{quest_name}'?")
      for i, h in enumerate(active_heroes, 1):
          print(f"({i}) {h} (Lv {heroes[h]['level']}, XP {heroes[h]['xp']})")
      print("(q) Cancel quest")

      choice = input("Pick a hero: ").lower()
      if choice == 'q':
          add_message("Cancelled quest.")
          return
    else:
      choice = 1

    try:
        h_idx = int(choice) - 1
        if h_idx < 0 or h_idx >= len(active_heroes):
            add_message("Invalid hero choice.")
            return
        hero_class = active_heroes[h_idx]
    except ValueError:
        add_message("Invalid input for hero choice.")
        return

    quests_today += 1
    hero_power = get_hero_combat_power(hero_class)
    hero_level = get_hero_level(hero_class)
    success_chance = difficulty + hero_power
    if success_chance > 95:
        success_chance = 95

    roll = random.randint(1, 100)
    if roll <= success_chance:
        add_message(f"Success on '{quest_name}'! (roll {roll} <= {success_chance})")
        if quest_name == "Gather Resources":
            gold_gain = random.randint((hero_level*10), (hero_level*10)+20)
            food_gain = random.randint(hero_level*5, hero_level*10)
            resources["Gold"] += gold_gain
            resources["Food"] += food_gain
            heroes[hero_class]["xp"] += 2
            add_message(f"Gained {gold_gain} Gold, {food_gain} Food, and 2 XP for {hero_class}.")
        elif quest_name == "Scout Hydra Location":
            if not hydra_progress["located"]:
                hydra_progress["located"] = True
                heroes[hero_class]["xp"] += 3
                add_message("Hydra's lair discovered! +3 XP")
            else:
                add_message("Already know where Hydra is. No new info.")
        elif quest_name == "Build Hydra Access Route":
            if hydra_progress["located"] and not hydra_progress["access"]:
                hydra_progress["access"] = True
                heroes[hero_class]["xp"] += 3
                add_message("Route to Hydra established! +3 XP")
            else:
                if not hydra_progress["located"]:
                    add_message("You don't know where Hydra is yet! No effect.")
                else:
                    add_message("Access already built.")
        elif quest_name == "Craft Hydra-Slaying Gear":
            if buildings["Blacksmith"] >= 2 or buildings["Arcane Tower"] >= 2:
                if not hydra_progress["gear"]:
                    hydra_progress["gear"] = True
                    heroes[hero_class]["xp"] += 3
                    add_message("Dragonsteel gear forged! +3 XP")
                else:
                    add_message("Gear already crafted.")
            else:
                add_message("Need at least Lv2 Blacksmith or Arcane Tower for gear.")
        if (hydra_progress["located"] and 
            hydra_progress["access"] and 
            hydra_progress["gear"]):
            hydra_progress["fight_unlocked"] = True
            add_message("All prerequisites met! Final battle unlocked.")
    else:
        add_message(f"Failure on '{quest_name}' (roll {roll} > {success_chance}). +1 XP to {hero_class}.")
        heroes[hero_class]["xp"] += 1

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
            victory()
            return
        elif your_team_hp <= 0:
            add_message("Your heroes have been defeated. Rebuild and try again.")
            return

def victory():
    add_message("Congratulations! The Hydra is slain, your kingdom is saved!")
    # You can keep playing or end.

# -------------------------------------------------------------------
# MAIN MENU
# -------------------------------------------------------------------

def main_menu():
    while True:
        # 1) Show the pinned status + any messages
        show_status_and_messages()
        # 2) Show the main action menu
        print("\nChoose an action:")
        print("(1) Build or Upgrade a structure")
        print("(2) Recruit or Train a hero")
        if quests_per_day > quests_today:
          print("(3) Send heroes on a quest")
        else:
        	print("(3) //Send heroes on a quest")
        if not hydra_progress['fight_unlocked']:
        	print("(4) //Attempt the final Hydra battle (if ready)")
        else:
        	print("(4) Attempt the final Hydra battle (if ready)")
        print("(5) End Day (resource collection & random events)")
        print("(q) Quit Game")

        choice = input("Enter choice: ").lower()
        if choice == '1':
            build_or_upgrade()
        elif choice == '2':
            recruit_or_train_hero()
        elif choice == '3':
            send_quest()
        elif choice == '4':
            attempt_final_battle()
        elif choice == '5':
            global turn_count
            turn_count += 1
            end_turn()
            add_message(f"Day {turn_count - 1} ended. Day {turn_count} begins.")
        elif choice == 'q':
            print("\nThanks for playing! Goodbye.")
            sys.exit(0)
        else:
            add_message("Invalid choice. Please try again.")

# -------------------------------------------------------------------
# ENTRY POINT
# -------------------------------------------------------------------
if __name__ == "__main__":
    clear_screen()
    print("Welcome to SLAY THE HYDRA!")
    print("Manage your kingdom, recruit heroes, and complete quests to find,")
    print("reach, and gear up for the Hydra. Good luck!")
    input("\nPress Enter to continue...")
    clear_screen()
    main_menu()
