# AUTOGENERATED! DO NOT EDIT! File to edit: ../../nbs/03.config.utils.ipynb.

# %% auto 0
__all__ = ["str_to_truck", "str_to_driver", "str_to_can_server", "str_to_trip_server"]

# %% ../../nbs/03.config.utils.ipynb 2
import re
from typing import Union

# %% ../../nbs/03.config.utils.ipynb 3
from .drivers import RE_DRIVER, Driver, drivers_by_id  # type: ignore
from data_io_nbdev.config.messengers import (
    CANMessenger,
    TripMessenger,  # type: ignore
    can_servers_by_host,
    can_servers_by_name,
    trip_servers_by_host,
    trip_servers_by_name,
)
from data_io_nbdev.config.vehicles import (
    RE_VIN,
    TruckInCloud,
    TruckInField,  # type: ignore
    trucks_by_id,
    trucks_by_vin,
)


# %% ../../nbs/03.config.utils.ipynb 4
def str_to_truck(
    truck_str: str,  # string of truch such as 'HMZABAAH7MF011058'  or "VB7",
) -> Union[TruckInCloud, TruckInField]:  #  TruckInCloud or TruckInField object
    """
    convert string to TruckInCloud or TruckInField object

    Parameter:

        truck_str: string of truch such as 'HMZABAAH7MF011058'  or "VB7",

    Return:

            truck: TruckInCloud or TruckInField
    """
    p = re.compile(RE_VIN)
    if p.match(truck_str):
        try:
            truck: Union[TruckInCloud, TruckInField] = trucks_by_vin[truck_str]
        except KeyError:
            raise KeyError(f"No Truck with VIN {truck_str}")
    else:
        try:
            truck: Union[TruckInCloud, TruckInField] = trucks_by_id.get(truck_str)  # type: ignore
        except KeyError:
            raise KeyError(f"No Truck with ID {truck_str}")

    return truck


# %% ../../nbs/03.config.utils.ipynb 5
def str_to_driver(
    driver_str: str,  # string of driver such as 'zheng-longfei'
) -> Driver:  #  Driver object
    """
    convert string to Driver object

    Parameter:

        driver_str: string of driver such as 'zheng-longfei'

    Return:

            driver: Driver object
    """
    p = re.compile(RE_DRIVER)
    assert p.match(driver_str), f"Invalid driver string: {driver_str}"
    try:
        driver: Driver = drivers_by_id[driver_str]
    except KeyError:
        raise KeyError(f"No Driver with ID {driver_str}")

    return driver


# %% ../../nbs/03.config.utils.ipynb 6
def str_to_can_server(
    can_server_str: str,  # string of can_server such as 'can_intra'
) -> CANMessenger:  # CANMessenger object
    """
    convert string to CANMessenger object

    Parameter:

        can_server_str: string of can_server such as 'can_intra'

    Return:

            can_server: CANMessenger object
    """
    try:
        can_server = can_servers_by_name[can_server_str]
    except KeyError:
        try:
            can_server = can_servers_by_host[can_server_str.split(":")[0]]
        except KeyError:
            raise KeyError(f"CAN server not found: {can_server_str}!")
    assert type(can_server) is CANMessenger, f"Wrong type for can_server {can_server}!"
    return can_server


# %% ../../nbs/03.config.utils.ipynb 7
def str_to_trip_server(
    trip_server_str: str,  # string of trip_server such as 'rocket_intra'
) -> TripMessenger:  # TripMessenger object
    """
    convert string to TripMessenger object

    Parameter:

        trip_server_str: string of trip_server such as 'rocket_intra'

    Return:

            trip_server: TripMessenger object
    """
    try:
        trip_server = trip_servers_by_name[trip_server_str]
    except KeyError:
        try:
            trip_server = trip_servers_by_host[trip_server_str.split(":")[0]]
        except KeyError:
            raise KeyError(f"Trip server not found: {trip_server_str}!")

    assert (
        type(trip_server) is TripMessenger
    ), f"Wrong type for trip_server {trip_server}!"
    return trip_server
