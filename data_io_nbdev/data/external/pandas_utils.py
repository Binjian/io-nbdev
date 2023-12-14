# AUTOGENERATED! DO NOT EDIT! File to edit: ../../../nbs/01.data.external.pandas_utils.ipynb.

# %% auto 0
__all__ = ['assemble_state_ser', 'assemble_reward_ser', 'assemble_flash_table', 'assemble_action_ser', 'nest',
           'df_to_nested_dict', 'eos_df_to_nested_dict', 'ep_nest', 'df_to_ep_nested_dict', 'avro_ep_encoding',
           'avro_ep_decoding', 'decode_mongo_records', 'decode_mongo_episodes', 'encode_dataframe_from_parquet',
           'decode_episode_batch_to_padded_arrays', 'encode_episode_dataframe_from_series',
           'recover_episodestart_tzinfo_from_timestamp']

# %% ../../../nbs/01.data.external.pandas_utils.ipynb 4
import math
from datetime import datetime
from functools import reduce
from typing import Dict, List, Optional, Tuple, Union, cast
from zoneinfo import ZoneInfo

# %% ../../../nbs/01.data.external.pandas_utils.ipynb 5
import numpy as np
import pandas as pd
import tensorflow as tf

# %% ../../../nbs/01.data.external.pandas_utils.ipynb 7
def assemble_state_ser(
    state_columns: pd.DataFrame,  # state_columns: Dataframe with columns ['timestep', 'velocity', 'thrust', 'brake']
        tz: ZoneInfo  # timezone for the timestamp
) -> Tuple[pd.Series, int]:  # state: Series with index ['rows', 'idx'], table_row_start: int
    """
    assemble state df from state_columns dataframe order is vital for the model
    
    inputs:
    
        state_columns: pd.DataFrame
    
    "timestep, velocity, thrust, brake"
    contiguous storage in each measurement
    due to sort_index, output:
    [col0: brake, col1: thrust, col2: timestep, col3: velocity]
    
    return:
    
        state: pd.Series
        table_row_start: int
    """

    # state_columns['timestep'] = pd.to_datetime(datetime.now().timestamp(), unit='us').tz_localize(tz)
    state: pd.Series = cast(
        pd.Series,
        (state_columns.stack().swaplevel(0, 1)),
    )
    state.name = "state"
    state.index.names = ["rows", "idx"]
    state.sort_index(
        inplace=True
    )  # sort by rows and idx (brake, thrust, timestep, velocity)
    # str_as_type = f"datetime64[us,{tz.key}]"  # type: ignore
    # state['timestep'].astype(str_as_type, copy=False)

    vel_stats = state["velocity"].astype("float").describe()

    # 0~20km/h; 7~30km/h; 10~40km/h; 20~50km/h; ...
    # average concept
    # 10; 18; 25; 35; 45; 55; 65; 75; 85; 95; 105
    #   13; 18; 22; 27; 32; 37; 42; 47; 52; 57; 62;
    # here upper bound rule adopted
    if vel_stats["max"] < 20:
        table_row_start = 0
    elif vel_stats["max"] < 30:
        table_row_start = 1
    elif vel_stats["max"] < 120:
        table_row_start = math.floor((vel_stats["max"] - 30) / 10) + 2
    else:
        table_row_start = 16  # cycle higher than 120km/h!
    # get the row of the table

    return state, table_row_start

# %% ../../../nbs/01.data.external.pandas_utils.ipynb 19
def assemble_reward_ser(
    power_columns: pd.DataFrame, obs_sampling_rate: int, ts
) -> pd.Series:
    """
    assemble reward df from motion_power df
    order is vital for the model:
    contiguous storage in each row, due to sort_index, output:
    power_columns: ['current', 'voltage']
    [timestep, work]
    """

    ui_sum = power_columns.prod(axis=1).sum()
    wh = (
        ui_sum / 3600.0 / obs_sampling_rate
    )  # rate 0.05 for kvaser, 0.02 remote # negative wh
    work = wh * (-1.0)
    reward: pd.Series = cast(
        pd.Series,
        (
            pd.DataFrame({"work": work, "timestep": ts}, index=[0])
            .stack()
            .swaplevel(0, 1)
            .sort_index()  # columns oder (timestep, work)
        ),
    )
    reward.name = "reward"
    reward.index.names = ["rows", "idx"]
    return reward

# %% ../../../nbs/01.data.external.pandas_utils.ipynb 20
def assemble_flash_table(
    torque_map_line: np.ndarray,
    table_start: int,
    torque_table_row_num_flash: int,
    torque_table_col_num: int,
    speed_scale: tuple,
    pedal_scale: tuple,
) -> pd.DataFrame:
    """
    generate flash table df from torque_map_line
    order is vital for the model:
    contiguous storage in each row, due to sort_index, output:
    "r0, r1, r2, r3, ..., speed, throttle(map),timestep"
    """
    # assemble_action_df

    speed_ser = pd.Series(
        speed_scale[table_start : table_start + torque_table_row_num_flash],
        name="speed",
    )
    throttle_ser = pd.Series(pedal_scale, name="throttle")
    torque_table = np.reshape(
        torque_map_line,
        [torque_table_row_num_flash, torque_table_col_num],
    )
    df_torque_table = pd.DataFrame(torque_table)  # not transpose!
    df_torque_table.index = speed_ser
    df_torque_table.columns = throttle_ser

    return df_torque_table

# %% ../../../nbs/01.data.external.pandas_utils.ipynb 21
def assemble_action_ser(
    torque_map_line: np.ndarray,
    torque_table_row_names: list[str],
    table_start: int,
    flash_start_ts: pd.Timestamp,
    flash_end_ts: pd.Timestamp,
    torque_table_row_num_flash: int,
    torque_table_col_num: int,
    speed_scale: tuple,
    pedal_scale: tuple,
    tz: ZoneInfo,
) -> pd.Series:
    """
    generate action df from torque_map_line
    order is vital for the model:
    contiguous storage in each row, due to sort_index, output:
    "r0, r1, r2, r3, ..., speed, throttle(map),timestep"
    """
    # assemble_action_df
    row_num = torque_table_row_num_flash

    speed_ser = pd.Series(
        speed_scale[table_start : table_start + torque_table_row_num_flash],
        name="speed",
    )
    throttle_ser = pd.Series(pedal_scale, name="throttle")
    torque_map = np.reshape(
        torque_map_line,
        [torque_table_row_num_flash, torque_table_col_num],
    )
    df_torque_map = pd.DataFrame(torque_map).transpose()  # row to columns
    df_torque_map.columns = pd.Index(torque_table_row_names)  # index: [r0, r1, ...]
    # df_torque_map.index = throttle_ser  # torque map index: if using [throttle], the index dtypes will become float!

    span_each_row = (flash_end_ts - flash_start_ts) / row_num
    flash_timestamps_ser = pd.Series(
        [
            pd.to_datetime(flash_start_ts + step * span_each_row, unit="us").tz_convert(
                tz
            )
            for step in np.linspace(1, row_num, row_num)
        ],
        name="timestep",
    )

    dfs: list[Union[pd.DataFrame, pd.Series]] = [
        df_torque_map,
        flash_timestamps_ser,
        speed_ser,
        throttle_ser,
    ]
    action_df: pd.DataFrame = cast(
        pd.DataFrame,
        reduce(
            lambda left, right: pd.merge(
                left,
                right,
                how="outer",
                left_index=True,
                right_index=True,
            ),
            dfs,
        ),
    )

    action = cast(
        pd.Series, (action_df.stack().swaplevel(0, 1).sort_index())
    )  # columns order (r0, r1, ..., speed, throttle, timestep)
    action.name = "action"
    action.index.names = ["rows", "idx"]
    # action.column.names = []

    return action

# %% ../../../nbs/01.data.external.pandas_utils.ipynb 22
def nest(d: dict) -> dict:
    """
    Convert a flat dictionary with tuple key to a nested dictionary through to the leaves
    arrays will be converted to dictionaries with the index as the key
    no conversion of pd.Timestamp
    only for use in mongo records
    """
    result: Dict = {}
    for key, value in d.items():
        target = result
        for k in key[:-1]:
            target = target.setdefault(k, {})
        target[str(key[-1])] = value  # for mongo only string keys are allowed.
    return result

# %% ../../../nbs/01.data.external.pandas_utils.ipynb 23
def df_to_nested_dict(df_multi_indexed_col: pd.DataFrame) -> dict:
    """
    Convert a dataframe with multi-indexed columns to a nested dictionary
    """
    d = df_multi_indexed_col.to_dict(
        "index"
    )  # for multi-indexed dataframe, the index in the first level of the dictionary is still a tuple!
    return {k: nest(v) for k, v in d.items()}

# %% ../../../nbs/01.data.external.pandas_utils.ipynb 24
def eos_df_to_nested_dict(episode: pd.DataFrame) -> dict:
    """
    Convert an eos dataframe with multi-indexed columns to a nested dictionary
    Remove all the levels of the multi-indexed columns except for 'timestamp'
    Keep only the timestamp as the single key for the nested dictionary
    """
    dict_nested = df_to_nested_dict(
        episode
    )  # for multi-indexed dataframe, the index in the first level of the dictionary is still a tuple!
    indices_dict = [
        {episode.index.names[i]: level for i, level in enumerate(levels)}
        for levels in episode.index
    ]  # all elements in the array should have the same vehicle, driver, episodestart
    single_key_dict = {
        idx["timestamp"]: dict_nested[key]
        for idx, key in zip(indices_dict, dict_nested)
    }

    return single_key_dict

# %% ../../../nbs/01.data.external.pandas_utils.ipynb 25
def ep_nest(d: Dict) -> Dict:
    """
    Convert a flat dictionary with tuple key to a nested dictionary with arrays at the leaves
    convert pd.Timestamp to millisecond long integer
    Timestamp with zoneinfo will be converted to UTC and then to millisecond long integer
    """
    result: Dict = {}
    for key, value in d.items():
        target = result
        for k in key[:-2]:
            target = target.setdefault(k, {})
        if key[-2] not in target:
            target[key[-2]] = []

        if isinstance(value, pd.Timestamp):
            value = value.timestamp() * 1e6  # convert to microsecond long integer,
        target[key[-2]].append(value)

    return result

# %% ../../../nbs/01.data.external.pandas_utils.ipynb 26
def df_to_ep_nested_dict(df_multi_indexed_col: pd.DataFrame) -> dict:
    """
    Convert a dataframe with multi-indexed columns to a nested dictionary
    """
    d = df_multi_indexed_col.to_dict(
        "index"
    )  # for multi-indexed dataframe, the index in the first level of the dictionary is still a tuple!
    return {k: ep_nest(v) for k, v in d.items()}

# %% ../../../nbs/01.data.external.pandas_utils.ipynb 27
def avro_ep_encoding(episode: pd.DataFrame) -> list[Dict]:
    """
    avro encoding,
    parsing requires a schema defined in "data_io/pool/episode_avro_schema.py"

    Convert an eos dataframe with multi-indexed columns to a nested dictionary
    Remove all the levels of the multi-indexed columns except for 'timestamp'
    Keep only the timestamp as the single key for the nested dictionary
    ! Convert Timestamp to millisecond long integer!! for compliance to the  avro storage format
    ! Timestamp with ZoneInfo will be converted to UTC and then to millisecond long integer
    as flat as possible
    PEP20: flat is better than nested!
    """
    dict_nested = df_to_ep_nested_dict(
        episode
    )  # for multi-indexed dataframe, the index in the first level of the dictionary is still a tuple!
    indices_dict = [
        {episode.index.names[i]: level for i, level in enumerate(levels)}
        for levels in episode.index
    ]  # all elements in the array should have the same vehicle, driver, episodestart
    array_of_dict = [
        {
            "timestamp": idx[
                "timestamp"
            ].timestamp()  # Timestamp with ZoneInfo will be converted to UTC
            * 1e6,  # convert to microsecond long integer
            **dict_nested[
                key
            ],  # merge the nested dict with the timestamp, as flat as possible
        }
        for (idx, key) in zip(indices_dict, dict_nested)
    ]

    return array_of_dict

# %% ../../../nbs/01.data.external.pandas_utils.ipynb 28
def avro_ep_decoding(episodes: list[Dict], tz_info: Optional[ZoneInfo]) -> pd.DataFrame:
    """
    avro decoding,

    Convert a list of nested dictionaries to DataFrame with multi-indexed columns and index
    ! Convert microsecond long integer to Timestamp!
    (avro storage format stores timestamp as long integer in keys but
    seem to have DateTime with timezone in the values.)

    Apache Avro store datetime/timestamp as timezone unaware (default as UTC)
    Therefore, we need tz info either in the metadata or elsewhere to designate the timezone

    sort the column order
    """

    batch = []
    for ep in episodes:
        dict_observations = [
            {
                (
                    ep["meta"]["episode_meta"]["vehicle"],
                    ep["meta"]["episode_meta"]["driver"],
                    pd.to_datetime(
                        ep["meta"]["episode_meta"]["episodestart"], unit="us", utc=True
                    ).tz_convert(tz_info),
                    pd.to_datetime(step["timestamp"], unit="us", utc=True).tz_convert(
                        tz_info
                    ),
                    qtuple,
                    rows,
                    idx,
                ): item
                if rows != "timestep"
                else pd.to_datetime(item, utc=True).tz_convert(tz_info)
                for qtuple, obs in step.items()
                if qtuple
                != "timestamp"  # "timestamp" is not a real valid qtuple, although it is in this level
                for rows, value in obs.items()  # but mixed in during avro encoding for storing
                for idx, item in enumerate(value)
            }
            for step in ep["sequence"]
        ]

        dict_ep = {k: v for d in dict_observations for k, v in d.items()}

        ser_decoded = pd.Series(dict_ep)
        ser_decoded.index.names = [
            "vehicle",
            "driver",
            "episodestart",
            "timestamp",
            "qtuple",
            "rows",
            "idx",
        ]
        df_decoded = ser_decoded.unstack(level=["qtuple", "rows", "idx"])  # type: ignore
        df_decoded.sort_index(inplace=True, axis=1)  # sort the column order
        batch.append(df_decoded)

    index_names = batch[0].index.names
    df_episodes = pd.concat(
        batch, keys=range(len(batch)), names=["batch"] + index_names
    )

    return df_episodes

# %% ../../../nbs/01.data.external.pandas_utils.ipynb 29
def decode_mongo_records(
    df: pd.DataFrame,
    torque_table_row_names: list[str],
) -> tuple[
    list[pd.DataFrame], list[pd.DataFrame], list[pd.DataFrame], list[pd.DataFrame]
]:
    """
    decoding the batch RECORD observations from mongodb nested dicts to pandas dataframe
    (EPISODE doesn't need decoding, it is already a dataframe)
    TODO need to check whether sort_index is necessary
    """

    dict_observations_list = (
        [  # list of observations as dict with tuple key suitable as MultiIndex
            {
                (
                    meta["episodestart"],
                    meta["vehicle"],
                    meta["driver"],
                    meta["timestamp"],
                    qtuple,
                    rows,
                    idx,
                ): value
                for qtuple, obs1 in obs.items()
                for rows, obs2 in obs1.items()
                for idx, value in obs2.items()
            }
            for meta, obs in zip(df["meta"], df["observation"])
        ]
    )

    df_actions = []
    df_states = []
    df_nstates = []
    ser_rewards = []
    idx = pd.IndexSlice
    for dict_observations in dict_observations_list:  # decode each measurement from
        ser_decoded = pd.Series(dict_observations)
        ser_decoded.index.names = [
            "episodestart",
            "vehicle",
            "driver",
            "timestamp",
            "qtuple",
            "rows",
            "idx",
        ]

        # decode state
        ser_state = ser_decoded.loc[
            idx[:, :, :, :, "state", ["brake", "thrust", "velocity", "timestep"]]
        ]
        df_state = ser_state.unstack(level=[0, 1, 2, 3, 4, 5])  # type: ignore
        multiindex = df_state.columns
        df_state.set_index(multiindex[-1], inplace=True)  # last index has timestep
        df_states.append(df_state)

        # decode action
        ser_action = ser_decoded.loc[
            idx[:, :, :, :, "action", [*torque_table_row_names, "throttle"]]
        ]
        df_action = ser_action.unstack(level=[0, 1, 2, 3, 4, 5])  # type: ignore
        multiindex = df_action.columns
        df_action.set_index(multiindex[-1], inplace=True)  # last index has throttle

        action_timestep = ser_decoded.loc[idx[:, :, :, :, "action", "timestep"]]
        action_speed = ser_decoded.loc[idx[:, :, :, :, "action", "speed"]]
        action_multi_col = [
            (*column, speed, timestep)  # swap speed and timestep
            for column, timestep, speed in zip(df_action.columns, action_timestep, action_speed)  # type: ignore
        ]
        df_action.columns = pd.MultiIndex.from_tuples(
            action_multi_col,
            names=[
                "episodestart",
                "vehicle",
                "driver",
                "timestamp",
                "qtuple",
                "rows",
                "speed",
                "timestep",
            ],
        )
        df_actions.append(df_action)

        # decode reward
        ser_reward = ser_decoded.loc[idx[:, :, :, :, "reward", ["work", "timestep"]]]
        df_reward = ser_reward.unstack([0, 1, 2, 3, 4, 5])  # type: ignore
        multiindex = df_reward.columns
        df_reward.set_index(multiindex[-1], inplace=True)  # last index has timestep
        # df_reward
        ser_rewards.append(df_reward)

        # decode nstate
        ser_nstate = ser_decoded.loc[
            idx[:, :, :, :, "nstate", ["brake", "thrust", "velocity", "timestep"]]
        ]
        df_nstate = ser_nstate.unstack([0, 1, 2, 3, 4, 5])  # type: ignore
        multiindex = df_nstate.columns
        df_nstate.set_index(multiindex[-1], inplace=True)
        df_nstates.append(df_nstate)

    return df_states, df_actions, ser_rewards, df_nstates

# %% ../../../nbs/01.data.external.pandas_utils.ipynb 30
def decode_mongo_episodes(
    df: pd.DataFrame,
) -> pd.DataFrame:
    """
    decoding the batch RECORD observations from mongodb nested dicts to pandas dataframe
    (EPISODE doesn't need decoding, it is already a dataframe)
    TODO need to check whether sort_index is necessary"""
    dict_observations = [
        {
            (
                meta["vehicle"],
                meta["driver"],
                meta["episodestart"],
                timestamp,
                qtuple,
                rows,
                idx,
            ): value
            for timestamp, obs1 in obs.items()
            for qtuple, obs2 in obs1.items()  # (state, action, reward, next_state)
            for rows, obs3 in obs2.items()  # (velocity, thrust, brake), (r0, r1, r2, ...),
            for idx, value in obs3.items()  # (0, 1, 2, ...)
        }
        for meta, obs in zip(df["meta"], df["observation"])
    ]

    batch = []
    for dict_obs in dict_observations:
        ser_decoded = pd.Series(dict_obs)
        ser_decoded.index.names = [
            "vehicle",
            "driver",
            "episodestart",
            "timestamp",
            "qtuple",
            "rows",
            "idx",
        ]
        df_decoded = ser_decoded.unstack(level=["qtuple", "rows", "idx"])  # type: ignore
        df_decoded.sort_index(inplace=True, axis=1)
        batch.append(df_decoded)  # qtuple, rows, index

    # batch.sort_index(inplace=True, axis=0)
    # must not sort_index, otherwise the order of the columns will be changed, if there were duplicated episodes
    index_names = batch[0].index.names
    df_episodes = pd.concat(
        batch, keys=range(len(batch)), names=["batch"] + index_names
    )
    return df_episodes

# %% ../../../nbs/01.data.external.pandas_utils.ipynb 31
def encode_dataframe_from_parquet(df: pd.DataFrame) -> pd.DataFrame:
    """
    decode the dataframe from parquet with flat column indices to MultiIndexed DataFrame
    """

    multi_tpl = [tuple(col.split("_")) for col in df.columns]
    multi_col = pd.MultiIndex.from_tuples(multi_tpl)
    i1 = multi_col.get_level_values(0)
    i1 = pd.Index(
        ["" if str(idx) in (str(pd.NA), "nan", "") else idx for idx in i1]
    )  # convert index of level 2 type to int and '' if NA
    i2 = multi_col.get_level_values(
        1
    )  # must be null string instead of the default pd.NA or np.nan
    i2 = pd.Index(
        ["" if str(idx) in (str(pd.NA), "nan", "") else idx for idx in i2]
    )  # convert index of level 2 type to int and '' if NA
    i3 = multi_col.get_level_values(
        2
    )  # must be null string instead of the default pd.NA or np.nan
    i3 = pd.Index(
        ["" if str(idx) in (str(pd.NA), "nan", "") else int(idx) for idx in i3]
    )  # convert index of level 2 type to int and '' if NA

    multi_col = pd.MultiIndex.from_arrays([i1, i2, i3])
    multi_col.names = ["qtuple", "rows", "idx"]
    df.columns = multi_col

    df = df.set_index(["vehicle", "driver", "episodestart", df.index])  # type: ignore

    return df

# %% ../../../nbs/01.data.external.pandas_utils.ipynb 32
def decode_episode_batch_to_padded_arrays(
    episodes: pd.DataFrame,
    torque_table_row_names: list[str],
    padding_value: float = -10000.0,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    decode the dataframes to 3D numpy arrays [B, T, F] for states, actions, rewards, next_states
    episodes with variable lengths will turn into ragged arrays with the same raggedness, thus the same maximum length
    after padding the arrays will have the same shape and padding pattern.

    episodes are not sorted and its internal index keeps the index order of the original episodes, not interleaved!
    idx_len_list: list of lengths of each episode in the batch, use explicit segmentation to avoid the bug,
    when the batch has duplicated episodes
    """

    # episodestart_index = episodes.index.unique(level='episode_start')
    # episodes.sort_index(inplace=False, axis=0).sort_index(inplace=True, axis=1)
    # array of rewards for minibatch
    # for ep in batch:
    #     ep.sort_index(inplace=True, axis=1)
    idx = pd.IndexSlice
    rewards_list = [
        episodes.loc[idx[i, :, :, :, :], idx["reward", "work"]].values.tolist()  # type: ignore
        for i in episodes.index.get_level_values(0)
    ]  # type: ignore
    r_n_t = tf.keras.utils.pad_sequences(
        rewards_list, padding="post", dtype=np.float32, value=padding_value
    )

    # array of states for minibatch
    states_list = [
        episodes.loc[idx[i, :, :, :, :], idx["state", ["velocity", "thrust", "brake"]]].values.tolist()  # type: ignore
        for i in episodes.index.get_level_values(0)
    ]  # type: ignore
    s_n_t = tf.keras.utils.pad_sequences(
        states_list, padding="post", dtype=np.float32, value=padding_value
    )

    # array of actions for minibatch
    actions_list = [
        episodes.loc[idx[i, :, :, :, :], idx["action", torque_table_row_names]].values.tolist()  # type: ignore
        for i in episodes.index.get_level_values(0)
    ]  # type: ignore
    a_n_t = tf.keras.utils.pad_sequences(
        actions_list, padding="post", dtype=np.float32, value=padding_value
    )

    # array of next_states for minibatch
    nstates_list = [
        episodes.loc[idx[i, :, :, :, :], idx["nstate", ["velocity", "thrust", "brake"]]].values.tolist()  # type: ignore
        for i in episodes.index.get_level_values(0)
    ]  # type: ignore
    ns_n_t = tf.keras.utils.pad_sequences(
        nstates_list, padding="post", dtype=np.float32, value=padding_value
    )

    return s_n_t, a_n_t, r_n_t, ns_n_t

# %% ../../../nbs/01.data.external.pandas_utils.ipynb 33
def encode_episode_dataframe_from_series(
    observations: List[pd.Series],
    torque_table_row_names: List[str],
    episode_start_dt: datetime,
    driver_str: str,
    truck_str: str,
) -> pd.DataFrame:
    """
    encode the list of observations as a dataframe with multi-indexed columns
    """
    episode = pd.concat(
        observations, axis=1
    ).transpose()  # concat along columns and transpose to DataFrame, columns not sorted as (s,a,r,s')
    episode.columns.names = ["tuple", "rows", "idx"]
    episode.set_index(("timestamp", "", 0), append=False, inplace=True)
    episode.index.name = "timestamp"
    episode.sort_index(axis=1, inplace=True)

    # convert columns types to float where necessary
    state_cols_float = [("state", col) for col in ["brake", "thrust", "velocity"]]
    action_cols_float = [
        ("action", col) for col in [*torque_table_row_names, "speed", "throttle"]
    ]
    reward_cols_float = [("reward", "work")]
    nstate_cols_float = [("nstate", col) for col in ["brake", "thrust", "velocity"]]
    for col in (
        action_cols_float + state_cols_float + reward_cols_float + nstate_cols_float
    ):
        episode[col[0], col[1]] = episode[col[0], col[1]].astype(
            "float"
        )  # float16 not allowed in parquet

    # Create MultiIndex ('vehicle', 'driver', 'episodestart', 'timestamp')
    ## Append index for the episode, in the order 'vehicle', 'driver', 'episodestart'
    episode = pd.concat(
        [episode],
        keys=[episode_start_dt],
        names=["episodestart"],
    )

    episode = pd.concat([episode], keys=[driver_str], names=["driver"])
    episode = pd.concat([episode], keys=[truck_str], names=["vehicle"])
    episode.sort_index(inplace=True)  # sorting in the time order of timestamps

    return episode

# %% ../../../nbs/01.data.external.pandas_utils.ipynb 34
def recover_episodestart_tzinfo_from_timestamp(
    ts: pd.Timestamp, tzinfo: ZoneInfo
) -> pd.Timestamp:
    """
    recover the timezone information from the parquet folder name string
    """

    ts = ts.tz_localize("UTC").tz_convert(tzinfo)

    return ts
