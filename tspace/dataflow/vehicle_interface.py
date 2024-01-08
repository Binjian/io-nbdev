# AUTOGENERATED! DO NOT EDIT! File to edit: ../../nbs/06.dataflow.vehicle_interface.ipynb.

# %% auto 0
__all__ = ['repo', 'VehicleInterface']

# %% ../../nbs/06.dataflow.vehicle_interface.ipynb 3
import abc
import concurrent.futures
import logging
import os
import git
import queue
import time
from pathlib import Path
from threading import Event, current_thread
from typing import Optional, Tuple
from dataclasses import dataclass
import numpy as np
import pandas as pd

# %% ../../nbs/06.dataflow.vehicle_interface.ipynb 4
from .consumer import Consumer  # type: ignore
from .filter.hetero import HeteroFilter  # type: ignore
from .pipeline.queue import Pipeline  # type: ignore
from .pipeline.deque import PipelineDQ  # type: ignore
from .producer import Producer  # type: ignore

# %% ../../nbs/06.dataflow.vehicle_interface.ipynb 5
from ..config.vehicles import Truck
from ..config.drivers import Driver
from ..config.messengers import CANMessenger
from ..data.core import RawType
from ..conn.tbox import TBoxCanException

# %% ../../nbs/06.dataflow.vehicle_interface.ipynb 6
repo = git.Repo("./", search_parent_directories=True)  # get the Repo object of tspace
if os.path.basename(repo.working_dir) != "tspace":  # I'm in the parent repo!
    repo = repo.submodule("tspace").module()
# print(repo.working_dir)

# %% ../../nbs/06.dataflow.vehicle_interface.ipynb 7
@dataclass(kw_only=True)
class VehicleInterface(
    Producer[RawType, str],
    Consumer[pd.DataFrame],
    HeteroFilter[RawType, pd.DataFrame],
):
    """
    VehicleInterface is an ABC. It's a Producer(get vehicle status), a Consumer(flasher) and a Filter(generate observation data)

    Args:

        truck: `Truck` object
        driver: `Driver` object
        can_server: `CANMessenger` object
        resume: resume from last table
        data_dir: data directory
        flash_count: flash count
        episode_count: episode count
        vcu_calib_table_row_start: vcu calibration table row start
        torque_table_default: default torque table
        torque_table_live: live torque table
        epi_countdown_time: episode countdown time
        capture_failure_count: count of caputure failure
        flash_failure_count: count of flash failure
        logger: logger
        dict_logger: dict logger
    """

    truck: Truck
    driver: Driver
    can_server: CANMessenger
    resume: bool = False
    data_dir: Optional[Path] = None
    flash_count: int = 0
    episode_count: int = 0
    vcu_calib_table_row_start: int = 0
    torque_table_default: Optional[pd.DataFrame] = None
    torque_table_live: Optional[pd.DataFrame] = None
    epi_countdown_time: float = 3.0
    capture_failure_count: int = 0
    flash_failure_count: int = 0
    logger: Optional[logging.Logger] = None
    dict_logger: Optional[dict] = None

    def __post_init__(self):
        self.logger = self.logger.getChild((self.__str__()))
        self.dict_logger = self.dict_logger

        if self.data_dir is None:
            self.data_dir = Path(".")
        self.init_vehicle()

        # super().__post_init__()
        self.logger.info("Vehicle interface initialized")

    def init_vehicle(self) -> None:
        """initialize vehicle interface. Flashing the vehicle with initial/default table."""
        proj_root = Path(repo.working_tree_dir)

        if self.resume:
            files = sorted(self.data_dir.glob("last_table*.csv"))
            if not files:
                self.logger.info(
                    f"{{'header': 'No last table found, start from default calibration table'}}",
                    extra=self.dict_logger,
                )
                latest_file = proj_root / "default_config" / "vb7_init_table.csv"
            else:
                self.logger.info(
                    f"{{'header': 'Resume last table'}}", extra=self.dict_logger
                )
                latest_file = max(files, key=os.path.getctime)

        else:
            self.logger.info(
                f"{{'header': 'Use default calibration table'}}",
                extra=self.dict_logger,
            )
            latest_file = proj_root / "default_config" / "vb7_init_table.csv"

        self.torque_table_default = pd.read_csv(latest_file, index_col=0)
        self.torque_table_default.columns = self.torque_table_default.columns.astype(
            np.float64
        )

        # pandas deep copy of the default table (while numpy shallow copy is sufficient)
        self.torque_table_live = self.torque_table_default.copy(
            deep=True
        )  # make sure it's a deep copy, the live table should be modified by the flash thread
        self.logger.info(
            f"{{'header': 'Start flash initial table'}}", extra=self.dict_logger
        )
        self.flash_vehicle(self.torque_table_default)

    @abc.abstractmethod
    def flash_vehicle(self, torque_table: pd.DataFrame) -> None:
        """Abstract method to flash the vehicle. Implemented by the concrete class `Kvaser` and `Cloud`."""
        pass

    def hmi_control(
        self,
        hmi_pipeline: Pipeline[str],  # input HMI pipeline
        observe_pipeline: Pipeline[pd.DataFrame],  # observation pipeline
        start_event: Event,  # input event start
        stop_event: Event,  # input event stop
        interrupt_event: Event,  # input event interrupt
        countdown_event: Event,  # input event countdown
        exit_event: Event,  # input event exit
        flash_event: Event,  # input event flash
    ) -> None:
        """HMI control logics by incoming events"""
        thread = current_thread()
        thread.name = "hmi_control"
        logger_hmi_control = self.logger.getChild("hmi_control")
        logger_hmi_control.propagate = True
        logger_hmi_control.info(
            f"{{'header': 'hmi_control thread start!'}}",
            extra=self.dict_logger,
        )

        while exit_event.is_set() is False:
            try:
                status = hmi_pipeline.get(
                    block=True, timeout=3.0
                )  # default block = True

            except TimeoutError:
                logger_hmi_control.info(
                    f"{{'header': 'hmi pipeline timeout'}}",
                    extra=self.dict_logger,
                )
                continue
            except queue.Empty:
                # logger_hmi_control.info(
                #     f"{{'header': 'hmi pipeline empty'}}",
                # )
                continue

            if status == "begin":
                observe_pipeline.clear()
                start_event.set()
                stop_event.clear()
                interrupt_event.clear()
                logger_hmi_control.info(
                    f"{{'header': 'Episode will start!!!'}}",
                    extra=self.dict_logger,
                )

            elif status == "end_valid":
                # set flag for countdown thread
                countdown_event.set()

                logger_hmi_control.info(
                    f"{{'header': 'Episode end starts countdown!'}}"
                )
            elif status == "end_invalid":
                start_event.clear()  # pause data collection
                interrupt_event.set()

                logger_hmi_control.info(
                    f"{{'header': 'Episode is interrupted!!!'}}",
                    extra=self.dict_logger,
                )
                observe_pipeline.clear()
                self.episode_count += 1  # invalid round increments
            elif status == "exit":
                start_event.clear()
                countdown_event.set()  # cancel countdown, let countdown thread exit

                observe_pipeline.clear()
                self.episode_count += 1
                interrupt_event.set()
                flash_event.set()  # set the flash event here for cruncher and kvaser/cloud filter thread
                countdown_event.set()  # cancel countdown, let countdown thread exit
                if not exit_event.is_set():
                    exit_event.set()
                break  # exit hmi control thread
        # exit hmi control thread
        logger_hmi_control.info(
            f"{{'header': 'HMI control dies!!!'}}", extra=self.dict_logger
        )

    @abc.abstractmethod
    def filter(
        self,
        in_pipeline: PipelineDQ[RawType],
        out_pipeline: Pipeline[pd.DataFrame],
        start_event: Optional[Event],
        stop_event: Optional[Event],
        interrupt_event: Optional[Event],  # input event
        flash_event: Optional[Event],
        exit_event: Optional[Event],
    ) -> None:
        """
        Produce data into the pipeline

        main entry to the capture thread
        sub-thread method
        """
        pass

    @abc.abstractmethod
    def init_internal_pipelines(
        self,
    ) -> Tuple[PipelineDQ[RawType], Pipeline[str]]:
        """
        Abstract method for initializing types of raw_pipeline and hmi_pipeline
        """
        pass

    def ignite(
        self,
        observe_pipeline: Pipeline[pd.DataFrame],  # observation pipeline
        flash_pipeline: Pipeline[pd.DataFrame],  # flash pipeline
        start_event: Event,  # input event start
        stop_event: Event,  #  input event stop
        interrupt_event: Event,  # input event interrupt
        flash_event: Event,  # input event flash
        exit_event: Event,  # input event exit
        watchdog_nap_time: float,  # watch dog nap time in seconds
        watchdog_capture_error_upper_bound: int,  # capture error limit to exit for watch dog
        watchdog_flash_error_upper_bound: int,  # flash error limit to exit for watch dog
    ):
        """
        creating the ThreadPool for handing the hmi, data capturing and data processing

        main entry to the vehicle thread. will spawn three further threads for
            - input processing, HMI control and output processing
            - data into the pipeline
            - handle the input pipeline
            - guide observation data into the output pipeline
            - start/stop/interrupt/countdown/exit event to control the state machine
        main entry to the capture thread
        """

        thread = current_thread()
        thread.name = "vehicle_interface_ignite"
        # internal pipelines, raw_pipelines are different for kvaser and cloud interface
        raw_pipeline, hmi_pipeline = self.init_internal_pipelines()

        # internal event
        countdown_event = Event()
        self.logger.info(
            f"{{'header': 'ignite Thread Pool starts!'}}", extra=self.dict_logger
        )

        with concurrent.futures.ThreadPoolExecutor(
            max_workers=6, thread_name_prefix="Vehicle_Interface"
        ) as executor:
            executor.submit(
                self.produce,
                raw_pipeline,
                hmi_pipeline,  # self.hmi_pipeline not required for cloud interface
                exit_event,
            )

            executor.submit(
                self.hmi_control,  # will delegate to concrete the hmi control method
                hmi_pipeline,
                observe_pipeline,
                start_event,
                stop_event,
                interrupt_event,
                countdown_event,
                exit_event,
                flash_event,
            )

            executor.submit(
                self.countdown,  # countdown thread
                observe_pipeline,
                start_event,
                countdown_event,
                stop_event,
                exit_event,
            )

            executor.submit(
                self.filter,
                raw_pipeline,
                observe_pipeline,
                start_event,
                stop_event,  # not used
                interrupt_event,  # not used
                flash_event,  # flash_event,
                exit_event,
            )

            executor.submit(
                self.consume,  # flash thread
                flash_pipeline,
                start_event,
                stop_event,
                interrupt_event,
                exit_event,
                flash_event,
            )

            executor.submit(
                self.watch_dog,  # observe thread (spawns 4 threads for input, HMI and output)
                countdown_event=countdown_event,
                exit_event=exit_event,
                watchdog_nap_time=watchdog_nap_time,  # watch dog will kick in after t seconds and send out exit signal.
                watchdog_capture_error_upper_bound=watchdog_capture_error_upper_bound,
                watchdog_flash_error_upper_bound=watchdog_flash_error_upper_bound,
            )
        # exit the thread
        self.logger.info(
            f"{{'header': 'ignite Thread Pool dies!'}}", extra=self.dict_logger
        )

    @abc.abstractmethod
    def produce(
        self,
        raw_pipeline: PipelineDQ[RawType],  # input pipeline for the raw data
        hmi_pipeline: Optional[
            Pipeline[str]
        ] = None,  # input pipeline for the hmi control
        exit_event: Optional[Event] = None,  # input event exit
    ):
        """
        Abstract method for producing data into the pipeline

        main entry to the capture thread
        will spawn three further threads for input processing, HMI control and output processing
        """
        pass

    def countdown(
        self,
        observe_pipeline: Pipeline[pd.DataFrame],  # output pipeline
        start_event: Event,  # output event
        countdown_event: Event,  # input event
        stop_event: Event,  # output event
        exit_event: Event,  # input event
    ):
        """countdown callback for the countdown thread"""
        thread = current_thread()
        thread.name = "countdown"
        logger_countdown = self.logger.getChild("countdown")
        logger_countdown.propagate = True
        logger_countdown.info(
            f"{{'header': 'countdown thread start!'}}", extra=self.dict_logger
        )

        while not exit_event.is_set():
            logger_countdown.info(
                f"{{'header': 'wait for countdown'}}", extra=self.dict_logger
            )
            countdown_event.wait()
            if exit_event.is_set():
                continue

            # if episode done is triggered, sleep for the extension time
            time.sleep(self.epi_countdown_time)
            # cancel wait as soon as waking up
            logger_countdown.info(
                f"{{'header': 'finish countdown'}}", extra=self.dict_logger
            )

            start_event.clear()
            stop_event.set()  # set valid stop signal only after countdown
            observe_pipeline.clear()
            self.episode_count += 1  # valid round increments

            logger_countdown.info(
                f"{{'header': 'Episode done! free remote_flash and remote_get!'}}",
                extra=self.dict_logger,
            )
            countdown_event.clear()
            # raise Exception("reset capture to stop")

        # exit countdown thread
        logger_countdown.info(
            f"{{'header': 'Coutndown dies!!!'}}", extra=self.dict_logger
        )

    def watch_dog(
        self,
        countdown_event: Event,  # watch dog need to send trigger signal to end count down thread
        exit_event: Event,  # input event
        watchdog_nap_time: float,  # nap time for watch dog
        watchdog_capture_error_upper_bound: int,  # upperbound for capture failure
        watchdog_flash_error_upper_bound: int,  # upperbound for flash failure
    ):
        """watch dog callback for the watch dog thread, after"""
        thread = current_thread()
        thread.name = "watch_dog"
        logger_wdog = self.logger.getChild("watch_dog")
        logger_wdog.propagate = True
        logger_wdog.info(
            f"{{'header': 'watch dog thread start!'}}", extra=self.dict_logger
        )

        while not exit_event.is_set():
            logger_wdog.info(
                f"{{'header': 'wait for watch dog timeout'}}", extra=self.dict_logger
            )

            # if episode done is triggered, sleep for the extension time
            time.sleep(watchdog_nap_time)
            # cancel wait as soon as waking up
            logger_wdog.info(
                f"{{'header': 'Watch dog time out！'}}", extra=self.dict_logger
            )
            if (
                self.capture_failure_count >= watchdog_capture_error_upper_bound
                or self.flash_failure_count >= watchdog_flash_error_upper_bound
            ):
                exit_event.set()  # set valid stop signal only after countdown
                countdown_event.set()

                logger_wdog.warning(
                    f"{{'header': 'watch dog kicks in!', "
                    f"'capture failure count': '{self.capture_failure_count}', "
                    f"'flash failure count': '{self.flash_failure_count}', "
                    f"'tail': 'system exit!'}}",
                    extra=self.dict_logger,
                )
            else:
                logger_wdog.info(
                    f"{{'header': 'watch dog kicks in!', "
                    f"'capture failure count': '{self.capture_failure_count}', "
                    f"'flash failure count': '{self.flash_failure_count}', "
                    f"'tail': 'system ok!'}}",
                    extra=self.dict_logger,
                )

        # exit countdown thread
        logger_wdog.info(f"{{'header': 'watch dog dies!!!'}}", extra=self.dict_logger)

    def consume(
        self,
        flash_pipeline: Pipeline[pd.DataFrame],  # flash pipeline
        start_event: Optional[Event] = None,  # input event start
        stop_event: Optional[Event] = None,  # input event stop
        interrupt_event: Optional[Event] = None,  # input event interrupt
        exit_event: Optional[Event] = None,  # input event exit
        flash_event: Optional[Event] = None,  # input event flash
    ):
        """
        Consume data from the pipeline

        main entry to the flash thread
        data in pipeline is a tuple of (torque_table, flash_start_row)
        """
        thread = current_thread()
        thread.name = "flash"
        flash_count = 0

        logger_flash = self.logger.getChild("flash")
        logger_flash.propagate = True

        logger_flash.info(
            f"{{'header': 'flash thread starts!'}}", extra=self.dict_logger
        )

        while not exit_event.is_set():
            if (
                not start_event.is_set()
                or interrupt_event.is_set()
                or stop_event.is_set()
            ):
                continue
            try:
                logger_flash.info(
                    f"{{'header': 'Flashing thread try to get a table!'}}",
                    extra=self.dict_logger,
                )

                table = flash_pipeline.get(
                    block=True, timeout=3
                )  # default block = True

            except TimeoutError:
                logger_flash.info(
                    f"{{'header': '{flash_count}' TableQueue timeout}}",
                    extra=self.dict_logger,
                )
                continue
            except queue.Empty:
                # if idle_count % 1000 == 0:
                #     logger_flash.info(
                #         f"{{'header': 'E{epi_cnt} step: {step_count}' TableQueue empty.}}",
                #         extra=self.dict_logger)))  # type: ignore
                # idle_count += 1
                continue
            else:
                # get change budget : % of initial table
                # dynamically get default table row as table.index changes
                table_default_reduced = self.torque_table_default.loc[table.index]
                torque_table_reduced = (
                    table * self.truck.torque_budget + table_default_reduced
                )

                torque_table_reduced.clip(
                    lower=table_default_reduced - self.truck.torque_budget,  # type: ignore
                    upper=table_default_reduced * self.truck.torque_upper_bound,  # type: ignore
                    inplace=True,
                )

                # create updated complete pedal map, only update the first few rows
                # torque_table_live keeps changing as the cache of the changing pedal map
                self.torque_table_live.loc[  # type: ignore
                    table.index
                ] = torque_table_reduced  # totally fine as pandas slicing operation! mypy is mean.

                logger_flash.info(
                    f"{{'header': 'flash starts'}}", extra=self.dict_logger
                )

                try:  # flash the vehicle
                    self.flash_vehicle(self.torque_table_live)
                except TBoxCanException as exc:
                    flash_event.set()  # set the flash event here for cruncher and kvaser/cloud filter thread
                    if exc.err_code == 4:  # xcp time out
                        logger_flash.info(
                            f"{{'header': 'Flash thread exception: {exc.codes[exc.err_code]}'}}",
                            extra=self.dict_logger,
                        )
                        interrupt_event.set()
                        continue
                    else:
                        logger_flash.error(
                            f"{{'header': 'Flash thread exception: {exc.codes[exc.err_code]}'}}",
                            extra=self.dict_logger,
                        )
                        exit_event.set()
                        raise exc

                except Exception as exc:
                    logger_flash.info(
                        f"{{'header': 'Flash thread exception: {exc}'}}",
                        extra=self.dict_logger,
                    )
                    raise exc

                flash_event.set()  # set the flash event here for cruncher and kvaser/cloud filter thread

                flash_count += 1
                logger_flash.info(
                    f"{{'header': 'flash ends', 'count': {flash_count} }}",
                    extra=self.dict_logger,
                )
                # watch(flash_count)

        if not flash_event.is_set():  # if flash event is not set, normal exit
            logger_flash.info(
                f"{{'header': 'flash_evnet is not set when exit occurred!!!!'}}",
                extra=self.dict_logger,
            )
            flash_event.set()  # set the flash event here for cruncher and kvaser/cloud filter thread
        else:  # if flash event is set, probably abnormal exit, GracefulKiller exit
            logger_flash.info(
                f"{{'header': 'flash_event is set'}}", extra=self.dict_logger
            )

        logger_flash.info(
            f"{{'header': 'Save the last table!!!!'}}", extra=self.dict_logger
        )
        last_table_store_path = (
            self.data_dir.joinpath(  # there's no slash in the end of the string
                "last_table_"
                + "-"
                + self.truck.vid
                + "-"
                + self.driver.pid
                + "-"
                + pd.Timestamp.now(self.truck.site.tz).isoformat()
                + ".csv"
            )
        )
        with open(last_table_store_path, "wb"):
            self.torque_table_live.to_csv(last_table_store_path)

        logger_flash.info(
            f"{{'header': 'flash thread dies!!!!'}}", extra=self.dict_logger
        )
