import random
import hlt
import math
import time as ptime
import numpy as np

from hlt import constants
from hlt.positionals import Direction
from hlt.positionals import Position
import logging #logs games

gohome = {} #contains boolean values for whether or not a ship should drop off materials
hasmove = {} #contains boolean values for whether or not a ship has a move yet
seed = {} #contains a random number 1 - 100 that is used to create variance in ship behavior
ship_target = {}  # contains a target for each ship sorted by list degree
dropoff_ships = {} #how many ships have been sent to drop off area
expensive = [] #sites of likely collisions

""" <<<Game Begin>>> """
game = hlt.Game()

game.ready("New Bot") # Starts the game. Only two seconds per turn.
logging.info("Successfully created bot! My Player ID is {}.".format(game.my_id)) # Logs ID

""" <<<Game Loop>>> """
raw_values = np.zeros((game.game_map.width, game.game_map.height)) #contains halite amount * inspiration for every tile

while True:
    start_time = ptime.time()

    game.update_frame() # Refresh game state
    me = game.me # Store player metadata and updated map metadata in me
    game_map = game.game_map
    ships = 0 #number of friendly ships
    dropoffs = 0  # number of dropoffs

    command_queue = [] # List that will contain all of the commands for the turn.
    position_choices = [] #contains all positions that have been chosen for collision avoidance
    enemy_pos = [] #will contain all possible positions enemies may be n next move
    enemy_current = [] #will contain all positions that enemies currently inhabit
    dropoff_targets = []  # going to label all areas of high halite that are far away from both my base and enemy bases

    spend = True #whether or not halite has been spent on the turn
    save = False #whether or not to save for
    build = True #whether or not to build a drop off at the target
    go = True #whether or not to send a ship to a possible drop off site

    total_hal = 0 #total amount of halite on map not counting collision sites

    e_layout = np.zeros((game_map.width, game_map.height)) #array of booleans to show enemy ships. 0 means none, 1 means enemy ship present.
    f_layout = np.zeros((game_map.width, game_map.height))  # array of booleans to show friendly ships. 0 means none, 1 means enemy ship present.
    inspired_spot = np.ones((game_map.width, game_map.height)) # grid of spaces with boolean values if they are inspired or not
    clump_weight = np.ones((game_map.width, game_map.height)) # grid of spaces that are good spots for drop offs
    enemies_in_rad = np.zeros((game_map.width, game_map.height))

    for player in game.players:
        if player != me.id:

            for ship in game.players[player].get_ships(): #creates array of number of ships within inspiration distance at each spot
                ly = ship.position.y - constants.INSPIRATION_RADIUS
                uy = ship.position.y + constants.INSPIRATION_RADIUS

                for a in range(5):
                    for b in range(a):
                        enemies_in_rad[(ship.position.x + b + 1) % game_map.width][(ly + a) % game_map.width] += 1
                        enemies_in_rad[(ship.position.x - b - 1) % game_map.width][(ly + a) % game_map.width] += 1
                for a in range(4):
                    for b in range(a):
                        enemies_in_rad[(ship.position.x + b + 1) % game_map.width][(uy - a) % game_map.width] += 1
                        enemies_in_rad[(ship.position.x - b - 1) % game_map.width][(uy - a) % game_map.width] += 1
                for a in range(9):
                    enemies_in_rad[ship.position.x][((ship.position.y - 4) + a) % game_map.width] += 1

                enemy_current.append(ship.position) # add current enemy position to current positions and all possible positions
                enemy_pos.append(ship.position)
                e_layout[ship.position.x][ship.position.y] = 1 #layout of enemy ships
                for cardinal in [Direction.North, Direction.South, Direction.East, Direction.West]:  # add all possible enemy positions for next turn for each possible direction
                    enemy_pos.append(game_map.normalize(Position(ship.position.x, ship.position.y).directional_offset(cardinal)))

    for ship in me.get_ships():
        ships += 1                                      #number of friendly ships
        f_layout[ship.position.x][ship.position.y] = 1  #layout of friendly ships
    for dropoff in me.get_dropoffs():
        dropoffs += 1                                   #number of friendly dropoffs

    e_ships = np.sum(e_layout)                          #number of enemy ships

    for x in range(game_map.width):
        for y in range(game_map.height):
            if raw_values[x][y] < game_map[Position(x, y)].halite_amount and game_map[Position(x, y)].halite_amount > 300 and game.turn_number > 8:
                for exp in expensive:
                    expensive.append(Position(x, y)) #collisons, spot has more halite than it did last turn

            raw_values[x][y] = game_map[Position(x, y)].halite_amount #set tile value equal to halite value

            if ships > 12 + (dropoffs * 5):          #if have enough ships, search for possible drop offs
                if game_map[Position(x, y)].halite_amount > (200 + (avg_hal * 2)) and game_map.calculate_distance(Position(x, y), game_map.closest_drop(me, Position(x, y))) > 15:
                    add = True
                    if len(dropoff_targets) > 0:
                        for d in range(len(dropoff_targets)):
                            if game_map.calculate_distance(dropoff_targets[d], game_map.closest_drop(me, Position(x, y))) < 14:
                                add = False          #don't add spot of it is close to another drop off target
                    if add:
                        ran = 7
                        xcoord = x - int(ran / 2)
                        ycoord = y - int(ran / 2)
                        conc = 0

                        for a in range(ran):
                            for b in range(ran):
                                conc += game_map[game_map.normalize(Position(xcoord + a, ycoord + b))].halite_amount  # calculate total amount of halite around possible drop off

                        if conc > (ran ** 2) * 320 and enemies_in_rad[x][y] <= 2: #if enough halite around area, mark as target and weight spot and adjacent spots to attract ships
                            clump_weight[x][y] = 2.8
                            clump_weight[(x + 1) % game_map.width][y] = 2
                            clump_weight[x][(y + 1) % game_map.width] = 2
                            clump_weight[(x - 1) % game_map.width][y] = 2
                            clump_weight[x][(y - 1) % game_map.width] = 2
                            dropoff_targets.append(Position(x, y))

    if len(dropoff_targets) > 0 and me.halite_amount < 4000: #make sure 4000 halite is had if a drop off needs to be built
        save = True

    col = 0
    total_hal = np.sum(raw_values)
    for pos in expensive:
        total_hal -= raw_values[pos.x][pos.y] #subtract collision sites from total_hal to avoid fluctuating average map halite
        col += 1

    avg_hal = total_hal / ((game_map.width * game_map.height) - col) #average amount of halite per square

    if len(game.players) == 2:
        min_hal = ((avg_hal / 1.8) + ((avg_hal / 100) * ((game_map.width ** 2) / 300)) * 1000 / (game.turn_number + 800)) + 3 #minimum halite ships should collect
    else:
        min_hal = ((avg_hal / 2.2) + ((avg_hal / 100) * ((game_map.width ** 2) / 300)) * 1000 / (game.turn_number + 800)) + 3 #varies based on total halite left on board. Greater left = searches for higher amounts

    for ship in me.get_ships(): #initailize all ships to have no move and make sure all ships have a seed and a target
        hasmove[str(ship.id)] = False
        try:
            seed[str(ship.id)] = seed[str(ship.id)]
        except:
            seed[str(ship.id)] = random.randint(0,100) #a random number to use to give ships variance to avoid clumping
        try:
            ship_target[str(ship.id)] = ship_target[str(ship.id)]  # if ship has a target, it will keep it, otherwise, it will be assigned one
        except KeyError:
            ship_target[str(ship.id)] = me.shipyard.position

    for ship in me.get_ships(): #ship stays still if it has insufficient halite to move
        if hasmove[str(ship.id)] == False:
            if game_map[ship.position].halite_amount / 10 > ship.halite_amount:
                command_queue.append(ship.move(Direction.Still))
                position_choices.append(ship.position)
                hasmove[str(ship.id)] = True

    for ship in me.get_ships(): #makes all ships go and drop off cargo in final turns, collide on shipyard
        if hasmove[str(ship.id)] == False:
            if constants.MAX_TURNS - game.turn_number < 15 and ship.position == game_map.closest_drop(me, ship.position):
                command_queue.append(ship.move(Direction.Still))
                hasmove[str(ship.id)] = True
            elif constants.MAX_TURNS - game.turn_number - ((seed[str(ship.id)] / 7) + 1) <= game_map.calculate_distance(ship.position, game_map.closest_drop(me, ship.position)):
                if game_map.calculate_distance(ship.position, game_map.closest_drop(me, ship.position)) > 5:
                    move = game_map.get_move(ship.position, game_map.closest_drop(me, ship.position), position_choices, enemy_current)
                else:
                    move = game_map.get_move(ship.position, game_map.closest_drop(me, ship.position), position_choices, [])
                command_queue.append(ship.move(move))
                if game_map.normalize(ship.position.directional_offset(move)) != game_map.closest_drop(me, ship.position):
                    position_choices.append(game_map.normalize(ship.position.directional_offset(move)))
                hasmove[str(ship.id)] = True

    for ship in me.get_ships(): #send ships home if they are full
        if hasmove[str(ship.id)] == False:
            if ship.halite_amount > 950:
                gohome[str(ship.id)] = True
                ship_target[str(ship.id)] = me.shipyard.position #not actually going to shipyard, might go to closer drop off. Shipyard is the default target and means ship needs assigned a new target
            if ship.halite_amount < 100:
                gohome[str(ship.id)] = False
            if gohome[str(ship.id)]:
                if game_map[ship.position].halite_amount > min_hal * 2 and constants.MAX_HALITE - ship.halite_amount > 50:
                    move = game_map.get_move(ship.position, game_map.closest_drop(me, ship.position), position_choices, enemy_pos, move = False, cheap= 0)
                else:
                    move = game_map.get_move(ship.position, game_map.closest_drop(me, ship.position), position_choices, enemy_pos, cheap= 0)
                command_queue.append(ship.move(move))
                position_choices.append(game_map.normalize(ship.position.directional_offset(move)))
                hasmove[str(ship.id)] = True

    if len(expensive) > 0: #finds closest ship to collision site and sends it there, setting aggression if enough other ships there to support
        for pos in expensive:
            not_targeted = True
            for tar in ship_target.values():
                if tar == pos:
                    not_targeted = False
            if game_map[pos].halite_amount < 200:
                expensive.remove(pos)
            elif not_targeted:
                logging.info(str(pos))
                try:
                    dis = 16
                    fship = None
                    for ship in me.get_ships():
                        if hasmove[str(ship.id)] == False and ship.halite_amount < 300:
                            if game_map.calculate_distance(ship.position, pos) < dis:
                                dis = game_map.calculate_distance(ship.position, pos)
                                fship = ship

                    ship_target[str(fship.id)] = pos
                    hasmove[str(fship.id)] = True
                except:
                    expensive.remove(pos)

    for ship in me.get_ships():
        if hasmove[str(ship.id)] == False:
            if game_map[ship.position].halite_amount + ship.halite_amount > 4000 and game.turn_number < 100:
                command_queue.append(ship.make_dropoff())
                hasmove[str(ship.id)] = True
                spend = False
        if hasmove[str(ship.id)] == False:
            inspired = 1
            if enemies_in_rad[ship_target[str(ship.id)].x][ship_target[str(ship.id)].y] >= 2:
                inspired = 3
            # if ship has the default target or its target now has less than min_hal, find it a target
            if ship_target[str(ship.id)] == me.shipyard.position or game_map[ship_target[str(ship.id)]].halite_amount <= (min_hal / inspired) + 3 or game_map[ship_target[str(ship.id)]].is_occupied:
                max = -1
                srange = int((65000/ships)**0.5)

                if srange > game_map.width:
                    srange = game_map.width

                sx = ship.position.x - int(srange / 2)
                sy = ship.position.y - int(srange / 2)
                best = None
                spot_values = np.zeros((game_map.width, game_map.height))

                for e in range(srange):
                    for f in range(srange):
                        x = (sx + e) % game_map.width
                        y = (sy + f) % game_map.height
                        inspired = 1
                        ha = game_map[Position(x, y)].halite_amount

                        if enemies_in_rad[x][y] >= 2:
                            inspired = 3
                        if ha > min_hal / inspired:
                            time = 0
                            while ha > min_hal / inspired:  # time is how many turns it will take before the halite goes down to min_hal
                                time += 1
                                ha = 0.75 * ha
                        else:
                            time = 10  # set time super high if no halite will be mined from the tile
                        if game_map[Position(x, y)].is_occupied: #set value to 0 if occupied, helps ships spread out and not go to spaces that may be taken by enemies
                            spot_values[x][y] = 0
                        elif avg_hal > 120 and len(game.players) == 2:
                            #calculates spot values based on halite per turn received for going to that space, with extra weight for dropoff areas, ignores inspiration for targeting early in 2p games
                            spot_values[x][y] = ((raw_values[x][y] - min_hal) * clump_weight[x][y]) / (game_map.calculate_distance(ship.position, Position(x, y)) + game_map.calculate_distance(Position(x, y), game_map.closest_drop(me, Position(x, y))) + time)  # set tile value equal to halite value / distance
                        else:
                            # calculates spot values based on halite per turn received for going to that space, with extra weight for dropoff areas
                            spot_values[x][y] = (((raw_values[x][y] * inspired) - min_hal) * clump_weight[x][y]) / (game_map.calculate_distance(ship.position, Position(x, y)) + game_map.calculate_distance(Position(x, y), game_map.closest_drop(me, Position(x, y))) + time)  # set tile value equal to halite value / distance

                for pos in ship_target.values():
                    spot_values[pos.x][pos.y] = 0 #helps ships spread out

                a = spot_values #Blurs map with a kernel in order to make cells values depend partially on the cells around them
                kernel = np.array([[0.5, 1.0, 0.5], [1.0, 8.0, 1.0], [0.5, 1.0, 0.5]])
                kernel = kernel / np.sum(kernel)
                arraylist = []
                for y in range(3):
                    temparray = np.copy(a)
                    temparray = np.roll(temparray, y - 1, axis=0)
                    for x in range(3):
                        temparray_X = np.copy(temparray)
                        temparray_X = np.roll(temparray_X, x - 1, axis=1) * kernel[y, x]
                        arraylist.append(temparray_X)
                arraylist = np.array(arraylist)
                arraylist_sum = np.sum(arraylist, axis=0)
                spot_values = arraylist_sum

                for e in range(srange):
                    for f in range(srange):
                        x = (sx + e) % game_map.width
                        y = (sy + f) % game_map.height
                        if spot_values[x][y] > max:
                            dup = any(a == Position(x, y) for a in ship_target.values()) #checks if target was already selected
                            if dup == False:
                                max = spot_values[x][y]
                                best = Position(x, y)
                ship_target[str(ship.id)] = best #set ship target to the best spot found

            best = ship_target[str(ship.id)]

            if game_map.calculate_distance(ship.position, game_map.closest_drop(me, ship.position)) > 18 and hasmove[str(ship.id)] == False:  # if ship can construct drop off here
                if me.halite_amount <= 4000:
                    save = True
                if me.halite_amount > 4000 - ship.halite_amount - game_map[ship.position].halite_amount and spend and game.turn_number <= (constants.MAX_TURNS - 140):

                    hal = 0
                    x = ship.position.x - 4
                    y = ship.position.y - 4
                    for i in range(9):
                        for j in range(9):
                            hal += game_map[game_map.normalize(Position(x + i, y + j))].halite_amount
                    if hal > 9 * 9 * 180 and game_map[ship.position].halite_amount > 0: #if area is good enough, make drop off
                        command_queue.append(ship.make_dropoff())
                        hasmove[str(ship.id)] = True
                        spend = False
            inspired = 1
            if enemies_in_rad[ship.position.x][ship.position.y] >= 2:
                inspired = 3

            if game_map[ship.position].halite_amount > int(min_hal / inspired) and hasmove[str(ship.id)] == False: #if current spot has enough halite
                if ship.halite_amount > 600:
                    move = game_map.get_move(ship.position, best, position_choices, enemy_pos, move=False, cheap= 1) #be more cautious of enemies if ship is very full
                else:
                    move = game_map.get_move(ship.position, best, position_choices, enemy_current, move=False, cheap= 1) #ignore where enemies might move to if collecting and have relatively low amount of halite
                command_queue.append(ship.move(move))
                position_choices.append(game_map.normalize(ship.position.directional_offset(move)))
                hasmove[str(ship.id)] = True
                if 0.75 * game_map[ship.position].halite_amount < int(min_hal / inspired):
                    ship_target[str(ship.id)] = me.shipyard.position

            if len(game.players) == 2 and hasmove[str(ship.id)] == False:
                ex = ship.position.x - 2 #x and y positions for looking for ships to ram
                ey = ship.position.y - 2
                for i in range(5):
                    for j in range(5):
                        if game_map[Position(ex + i, ey + j)].is_occupied:
                            if game_map[Position(ex + i, ey + j)].ship.owner != me.id:
                                ram = ship.halite_amount < game_map[Position(ex + i, ey + j)].ship.halite_amount + game_map[Position(ex + i, ey + j)].halite_amount \
                                      and game_map.calculate_distance(game_map[Position(ex + i, ey + j)].ship.position, game_map.closest_drop(me, ship.position)) \
                                      < game_map.calculate_distance(game_map[Position(ex + i, ey + j)].ship.position, game_map.closest_drop(game.players[game_map[Position(ex + i, ey + j)].ship.owner], game_map[Position(ex + i, ey + j)].ship.position))
                                    # aggression in two player games, crash ships if enemy has more halite and is closer to friendly base, and is close enough
                                ran = 15
                                xc = ship.position.x - int(ran / 2)
                                yc = ship.position.y - int(ran / 2)
                                f_num = 0

                                for c in range(ran):
                                    for d in range(ran):
                                        f_num += f_layout[(xc + c) % game_map.width][(yc + d) % game_map.height]

                                if f_num <= 3:
                                    ram = False #don't ram if no friendlies in area

                                if ram and hasmove[str(ship.id)] == False:
                                    move = game_map.get_move(ship.position, Position(ex + i, ey + j), position_choices, [])
                                    command_queue.append(ship.move(move))
                                    position_choices.append(game_map.normalize(ship.position.directional_offset(move)))
                                    hasmove[str(ship.id)] = True

            if hasmove[str(ship.id)] == False:
                if game_map[ship.position].halite_amount < 6 / inspired:
                    move = game_map.get_move(ship.position, best, position_choices, enemy_current, cheap = 1)
                else:
                    move = game_map.get_move(ship.position, best, position_choices, enemy_pos, cheap = 1)
                command_queue.append(ship.move(move))
                position_choices.append(game_map.normalize(ship.position.directional_offset(move)))
                hasmove[str(ship.id)] = True

    #constraints for ship spawning
    if game.turn_number <= (constants.MAX_TURNS - (120 + (len(game.players) * 20))) + (((game_map.width ** 2 / 32 ** 2) * 5)) and me.halite_amount >= constants.SHIP_COST and avg_hal > 80:
        spawn = True
        for p in range(len(position_choices)):
            if position_choices[p] == me.shipyard.position: #don't spawn ship if shipyard is occupied
                spawn = False
        if spawn and save == False and spend:
            command_queue.append(me.shipyard.spawn())
    game.end_turn(command_queue)# Ends turn by sending commands to the game environment
