import OpenNero
import common
import constants
from BlocksTower.environment import TowerEnvironment
import BlocksTower.agent

class TowerMod:
    # initializer
    def __init__(self):
        print 'Creating TowerMod'
        self.environment = None
        self.agent_id = None # the ID of the agent
        self.marker_map = {} # a map of cells and markers so that we don't have more than one per cell
        self.marker_states = {} # states of the marker agents that run for one cell and stop
        self.agent_map = {} # agents active on the map
        self.wall_ids = [] # walls on the map

    def __del__(self):
        print 'Deleting TowerMod'

    # add a set of coordinate axes
    def addAxes(self):
        OpenNero.getSimContext().addAxes()

    def add_maze(self):
        """Add a randomly generated maze"""
        if self.environment:
            print "ERROR: Environment already created"
            return
        self.set_environment(TowerEnvironment())

    def set_environment(self,env):
        self.environment = env
        for id in self.wall_ids: # delete the walls
            common.removeObject(id)
        del self.wall_ids[:] # clear the ids
        OpenNero.set_environment(env)

        common.addObject("data/shapes/cube/WhiteCube.xml", OpenNero.Vector3f(1 * constants.GRID_DX, 2 * constants.GRID_DY, 0 * constants.GRID_DZ), OpenNero.Vector3f(0,0,0), scale=OpenNero.Vector3f(.25,.25,4))
        common.addObject("data/shapes/cube/WhiteCube.xml", OpenNero.Vector3f(2 * constants.GRID_DX, 2 * constants.GRID_DY, 0 * constants.GRID_DZ), OpenNero.Vector3f(0,0,0), scale=OpenNero.Vector3f(.25,.25,4))
        common.addObject("data/shapes/cube/WhiteCube.xml", OpenNero.Vector3f(3 * constants.GRID_DX, 2 * constants.GRID_DY, 0 * constants.GRID_DZ), OpenNero.Vector3f(0,0,0), scale=OpenNero.Vector3f(.25,.25,4))

    def num_towers(self):
        return num_towers

    def start_tower1(self):
        """ start the tower demo """
        self.num_towers = 3
        OpenNero.disable_ai()
        self.stop_agent()
        self.set_environment(TowerEnvironment())
        self.agent_id = common.addObject("data/shapes/character/BlocksRobot.xml", OpenNero.Vector3f(constants.GRID_DX, constants.GRID_DY, 2), type=constants.AGENT_MASK, scale=OpenNero.Vector3f(3,3,3))
        OpenNero.enable_ai()

    def start_tower2(self):
        """ start the tower demo """
        self.num_towers = 3
        OpenNero.disable_ai()
        self.stop_agent()
        self.set_environment(TowerEnvironment())
        self.agent_id = common.addObject("data/shapes/character/BlocksRobot2.xml", OpenNero.Vector3f(constants.GRID_DX, constants.GRID_DY, 2), type=constants.AGENT_MASK, scale=OpenNero.Vector3f(3,3,3))
        OpenNero.enable_ai()

    def start_tower3(self):
        """ start the tower demo """
        self.num_towers = 2
        OpenNero.disable_ai()
        self.stop_agent()
        self.set_environment(TowerEnvironment())
        self.agent_id = common.addObject("data/shapes/character/BlocksRobot3.xml", OpenNero.Vector3f(constants.GRID_DX, constants.GRID_DY, 2), type=constants.AGENT_MASK, scale=OpenNero.Vector3f(3,3,3))
        OpenNero.enable_ai()
        
    def stop_agent(self):
        if self.agent_id is not None:
            common.removeObject(self.agent_id)
        self.agent_id = None

    def control_fps(self,key):
        FirstPersonAgent.key_pressed = key

    def set_speedup(self, speedup):
        print 'Speedup set to', speedup
        # speed up between 0 (delay set to 1 second) and 1 (delay set to 0)
        OpenNero.getSimContext().delay = 1.0 - speedup

gMod = None

def delMod():
    global gMod
    gMod = None

def getMod():
    global gMod
    if not gMod:
        gMod = TowerMod()
    return gMod
