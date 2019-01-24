import queue

from . import constants
from .entity import Entity, Shipyard, Ship, Dropoff
from .positionals import Direction, Position
from .common import read_input

import logging
import random
import time
class Player:
    """
    Player object containing all items/metadata pertinent to the player.
    """
    def __init__(self, player_id, shipyard, halite=0):
        self.id = player_id
        self.shipyard = shipyard
        self.halite_amount = halite
        self._ships = {}
        self._dropoffs = {}

    def get_ship(self, ship_id):
        """
        Returns a singular ship mapped by the ship id
        :param ship_id: The ship id of the ship you wish to return
        :return: the ship object.
        """
        return self._ships[ship_id]

    def get_ships(self):
        """
        :return: Returns all ship objects in a list
        """
        return list(self._ships.values())

    def get_dropoff(self, dropoff_id):
        """
        Returns a singular dropoff mapped by its id
        :param dropoff_id: The dropoff id to return
        :return: The dropoff object
        """
        return self._dropoffs[dropoff_id]

    def get_dropoffs(self):
        """
        :return: Returns all dropoff objects in a list
        """
        return list(self._dropoffs.values())

    def has_ship(self, ship_id):
        """
        Check whether the player has a ship with a given ID.

        Useful if you track ships via IDs elsewhere and want to make
        sure the ship still exists.

        :param ship_id: The ID to check.
        :return: True if and only if the ship exists.
        """
        return ship_id in self._ships


    @staticmethod
    def _generate():
        """
        Creates a player object from the input given by the game engine
        :return: The player object
        """
        player, shipyard_x, shipyard_y = map(int, read_input().split())
        return Player(player, Shipyard(player, -1, Position(shipyard_x, shipyard_y)))

    def _update(self, num_ships, num_dropoffs, halite):
        """
        Updates this player object considering the input from the game engine for the current specific turn.
        :param num_ships: The number of ships this player has this turn
        :param num_dropoffs: The number of dropoffs this player has this turn
        :param halite: How much halite the player has in total
        :return: nothing.
        """
        self.halite_amount = halite
        self._ships = {id: ship for (id, ship) in [Ship._generate(self.id) for _ in range(num_ships)]}
        self._dropoffs = {id: dropoff for (id, dropoff) in [Dropoff._generate(self.id) for _ in range(num_dropoffs)]}


class MapCell:
    """A cell on the game map."""
    def __init__(self, position, halite_amount):
        self.position = position
        self.halite_amount = halite_amount
        self.ship = None
        self.structure = None

    @property
    def is_empty(self):
        """
        :return: Whether this cell has no ships or structures
        """
        return self.ship is None and self.structure is None

    @property
    def is_occupied(self):
        """
        :return: Whether this cell has any ships
        """
        return self.ship is not None

    @property
    def has_structure(self):
        """
        :return: Whether this cell has any structures
        """
        return self.structure is not None

    @property
    def structure_type(self):
        """
        :return: What is the structure type in this cell
        """
        return None if not self.structure else type(self.structure)

    def mark_unsafe(self, ship):
        """
        Mark this cell as unsafe (occupied) for navigation.

        Use in conjunction with GameMap.naive_navigate.
        """
        self.ship = ship

    def __eq__(self, other):
        return self.position == other.position

    def __ne__(self, other):
        return not self.__eq__(other)

    def __str__(self):
        return 'MapCell({}, halite={})'.format(self.position, self.halite_amount)


class GameMap:
    """
    The game map.

    Can be indexed by a position, or by a contained entity.
    Coordinates start at 0. Coordinates are normalized for you
    """
    def __init__(self, cells, width, height):
        self.width = width
        self.height = height
        self._cells = cells

    def __getitem__(self, location):
        """
        Getter for position object or entity objects within the game map
        :param location: the position or entity to access in this map
        :return: the contents housing that cell or entity
        """
        if isinstance(location, Position):
            location = self.normalize(location)
            return self._cells[location.y][location.x]
        elif isinstance(location, Entity):
            return self._cells[location.position.y][location.position.x]
        return None

    def calculate_distance(self, source, target):
        """
        Compute the Manhattan distance between two locations.
        Accounts for wrap-around.
        :param source: The source from where to calculate
        :param target: The target to where calculate
        :return: The distance between these items
        """
        source = self.normalize(source)
        target = self.normalize(target)
        resulting_position = abs(source - target)
        return min(resulting_position.x, self.width - resulting_position.x) + \
            min(resulting_position.y, self.height - resulting_position.y)

    def normalize(self, position):
        """
        Normalized the position within the bounds of the toroidal map.
        i.e.: Takes a point which may or may not be within width and
        height bounds, and places it within those bounds considering
        wraparound.
        :param position: A position object.
        :return: A normalized position object fitting within the bounds of the map
        """
        return Position(position.x % self.width, position.y % self.height)

    @staticmethod
    def _get_target_direction(source, target):
        """
        Returns where in the cardinality spectrum the target is from source. e.g.: North, East; South, West; etc.
        NOTE: Ignores toroid
        :param source: The source position
        :param target: The target position
        :return: A tuple containing the target Direction. A tuple item (or both) could be None if within same coords
        """
        return (Direction.South if target.y > source.y else Direction.North if target.y < source.y else None,
                Direction.East if target.x > source.x else Direction.West if target.x < source.x else None)

    def closest_drop(self, me, ship):
        closest = me.shipyard.position
        for drop in me.get_dropoffs():
            drop = drop.position
            if self.calculate_distance(ship, drop) < self.calculate_distance(ship, closest):
                closest = drop
        return closest

    def get_move(self, source, destination, full, enemies, move = True, cheap = 2):
        """
        Return the move closer to the target point, taking into account friendly positions and enemy positions

        source: current position of ship
        destination: target tile
        full: array of positions occupied by friendlies next turn
        enemies: array of enemies, empty if aggressive, all possible enemy positions if cautious, current enemy positions otherwise
        move: False if ship wants to mine current spot
        cheap: 0 means go for cheapest of possible spots, 1 means go for expensive, default 2 means random
        """

        y = 0 #will stay zero if both x and y travel is needed
        source = self.normalize(source)
        destination = self.normalize(destination)

        possible_moves = []
        distance = abs(destination - source)
        y_cardinality, x_cardinality = self._get_target_direction(source, destination)

        if move == False:
            possible_moves.append(Direction.Still) #make sure top ship priority is to stay still if move == False

        if distance.x != 0:
            possible_moves.append(x_cardinality if distance.x < (self.width / 2)
                                  else Direction.invert(x_cardinality))
        else:
            y = 1 #means no x travel is needed
        if distance.y != 0:
            possible_moves.append(y_cardinality if distance.y < (self.height / 2)
                                  else Direction.invert(y_cardinality))
        else:
            y = 2 #means no y travel is needed

        if source == destination:
            y = 3 #means already at destination


        if y == 3:
            if move:
                possible_moves.append(Direction.Still)
            possible_moves.append(Direction.West)
            possible_moves.append(Direction.North)
            possible_moves.append(Direction.East)
            possible_moves.append(Direction.South)

        if y == 0:
            if move:
                if cheap == 0: #means ship wants cheapest
                    if self[source.directional_offset(possible_moves[0])].halite_amount > self[source.directional_offset(possible_moves[1])].halite_amount:
                        temp = possible_moves[0]
                        possible_moves[0] = possible_moves[1]
                        possible_moves[1] = temp

                elif cheap == 1:  # means ship wants most expensive
                    if self[source.directional_offset(possible_moves[0])].halite_amount < self[source.directional_offset(possible_moves[1])].halite_amount:
                        temp = possible_moves[0]
                        possible_moves[0] = possible_moves[1]
                        possible_moves[1] = temp

                else: #means ship has no preference, picks randomly to avoid directional bias
                    if random.randint(0, 2) == 1:
                        temp = possible_moves[0]
                        possible_moves[0] = possible_moves[1]
                        possible_moves[1] = temp
                possible_moves.append(Direction.Still)
                possible_moves.append(Direction.invert(possible_moves[0]))
                possible_moves.append(Direction.invert(possible_moves[1]))
            else:
                if random.randint(0,2) == 1:
                    temp = possible_moves[1]
                    possible_moves[1] = possible_moves[2]
                    possible_moves[2] = temp
                possible_moves.append(Direction.invert(possible_moves[1]))
                possible_moves.append(Direction.invert(possible_moves[2]))

        elif y == 1:
            if random.randint(0, 2) == 1:
                possible_moves.append(Direction.West)
            else:
                possible_moves.append(Direction.East)
            if move:
                possible_moves.append(Direction.invert(possible_moves[1]))
                possible_moves.append(Direction.Still)
                possible_moves.append(Direction.invert(possible_moves[0]))
            else:
                possible_moves.append(Direction.invert(possible_moves[2]))
                possible_moves.append(Direction.invert(possible_moves[1]))

        elif y == 2:
            if random.randint(0, 2) == 1:
                possible_moves.append(Direction.North)
            else:
                possible_moves.append(Direction.South)
            if move:
                possible_moves.append(Direction.invert(possible_moves[1]))
                possible_moves.append(Direction.Still)
                possible_moves.append(Direction.invert(possible_moves[0]))
            else:
                possible_moves.append(Direction.invert(possible_moves[2]))
                possible_moves.append(Direction.invert(possible_moves[1]))

        coord = []

        for a in range(len(possible_moves)):
            coord.append(self.normalize(source.directional_offset(possible_moves[a])))

        m = 0
        while m < len(possible_moves): #take out moves that conflict with others
            search = True
            for n in range(len(full)):
                if search:
                    if coord[m] == full[n] and search:
                        del possible_moves[m]
                        del coord[m]
                        search = False
            if search:
                m += 1

        avoid_enemies = []
        for j in range(len(possible_moves)):
            avoid_enemies.append(possible_moves[j])

        coord = []
        for a in range(len(avoid_enemies)):
            coord.append(self.normalize(source.directional_offset(avoid_enemies[a])))

        m = 0
        while m < len(avoid_enemies): #try to avoid enemies if possible
            search = True
            for n in range(len(enemies)):
                if search:
                    if coord[m] == enemies[n] and search:
                        del avoid_enemies[m]
                        del coord[m]
                        search = False
            if search:
                m += 1

        if len(avoid_enemies) > 0: #send move that avoids enemies specified if possible
            return avoid_enemies[0]

        elif len(possible_moves) > 0:
            return possible_moves[0]
        else:
            logging.info('ERROR: no free space found!')
            return Direction.East #collision fixing system needs added

    @staticmethod
    def _generate():
        """
        Creates a map object from the input given by the game engine
        :return: The map object
        """
        map_width, map_height = map(int, read_input().split())
        game_map = [[None for _ in range(map_width)] for _ in range(map_height)]
        for y_position in range(map_height):
            cells = read_input().split()
            for x_position in range(map_width):
                game_map[y_position][x_position] = MapCell(Position(x_position, y_position),
                                                           int(cells[x_position]))
        return GameMap(game_map, map_width, map_height)

    def _update(self):
        """
        Updates this map object from the input given by the game engine
        :return: nothing
        """
        # Mark cells as safe for navigation (will re-mark unsafe cells
        # later)
        for y in range(self.height):
            for x in range(self.width):
                self[Position(x, y)].ship = None

        for _ in range(int(read_input())):
            cell_x, cell_y, cell_energy = map(int, read_input().split())
            self[Position(cell_x, cell_y)].halite_amount = cell_energy
