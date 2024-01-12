from managers.translate_manager import _
from tasks.power.power import Power
from tasks.power.instance import Instance
from .doubleactivity import DoubleActivity


class GardenOfPlenty(DoubleActivity):
    def __init__(self, name, enabled, instance_type, instance_names):
        super().__init__(name, enabled)
        self.instance_type = instance_type
        self.instance_names = instance_names

    def _run_instances(self, reward_count):
        instance_type = self.instance_type
        instance_name = self.instance_names[instance_type]
        instance_power_max = 60
        instance_power_min = 10

        power = min(Power.get(), reward_count * instance_power_min)

        full_runs = power // instance_power_max
        if full_runs:
            Instance.run(instance_type, instance_name, instance_power_max, full_runs)

        partial_run_power = power % instance_power_max
        if partial_run_power >= instance_power_min:
            Instance.run(instance_type, instance_name, partial_run_power, 1)
