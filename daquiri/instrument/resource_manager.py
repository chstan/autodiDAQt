import os
import visa

__all__ = ('resource_manager',)

dirpath = os.path.dirname(os.path.realpath(__file__))
simulation_file_path = os.path.join(dirpath, 'sim/simulated.yaml')
resource_manager = visa.ResourceManager('{}@sim'.format(simulation_file_path))
