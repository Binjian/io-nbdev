# AUTOGENERATED! DO NOT EDIT! File to edit: ../../nbs/03.config.db.ipynb.

# %% ../../nbs/03.config.db.ipynb 2
from __future__ import annotations
import re
from collections import namedtuple

# %% auto 0
__all__ = ['RE_DB_KEY', 'DBConfig', 'db_config_list', 'db_config_servers_by_name', 'db_config_servers_by_host', 'get_db_config']

# %% ../../nbs/03.config.db.ipynb 3
# Define TypedDict for type hinting of typed collections: records and episodes
RE_DB_KEY = r"^[A-Za-z]\w*:\w+@\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d{1,5}"

# %% ../../nbs/03.config.db.ipynb 4
DBConfig = namedtuple(
    "DBConfig",
    [
        "server_name",  # name of the server
        "database_name",  # name of the database
        "collection_name",  # name of the collection
        "host",  # host name for the database server
        "port",  # port for the database server
        "user_name",  # username for the database server
        "password",  # password for the database server
        "proxy",  # proxy for the database server
        "type",  # type of the collection # : Record or Episode, default as RECORD, can be changed to EPISODE at runtime
    ],
)

# %% ../../nbs/03.config.db.ipynb 5
db_config_list = [
    DBConfig(
        server_name="default",  # name of the database
        database_name="eos",  # name of the database
        collection_name="coll_records",  # name of the collection
        host="127.0.0.1",  # url for the database server
        port="27017",  # port for the database server
        user_name="",  # username for the database server
        password="",  # password for the database server
        proxy="",  # proxy for the database server
        type="RECORD",
    ),
    DBConfig(
        server_name="mongo_local",  # name of the database
        database_name="eos_dill",  # name of the database
        collection_name="coll_episodes",  # name of the collection
        host="127.0.0.1",  # url for the database server
        port="27017",  # port for the database server
        user_name="",  # username for the database server
        password="",  # password for the database server
        proxy="",  # proxy for the database server
        type="RECORD",
    ),
    DBConfig(
        server_name="mongo_record",  # name of the database
        database_name="eos_dill",  # name of the database
        collection_name="coll_record_zone2",  # name of the collection
        host="127.0.0.1",  # url for the database server
        port="27017",  # port for the database server
        user_name="",  # username for the database server
        password="",  # password for the database server
        proxy="",  # proxy for the database server
        type="RECORD",
    ),
    DBConfig(
        server_name="mongo_episode",  # name of the database
        database_name="eos",  # name of the database
        collection_name="coll_episode",  # name of the collection
        host="127.0.0.1",  # url for the database server
        port="27017",  # port for the database server
        user_name="",  # username for the database server
        password="",  # password for the database server
        proxy="",  # proxy for the database server
        type="EPISODE",
    ),
    DBConfig(
        server_name="mongo_episode_road",  # name of the database
        database_name="eos",  # name of the database
        collection_name="coll_episode_road",  # name of the collection
        host="127.0.0.1",  # url for the database server
        port="27017",  # port for the database server
        user_name="",  # username for the database server
        password="",  # password for the database server
        proxy="",  # proxy for the database server
        type="EPISODE",
    ),
    DBConfig(
        server_name="mongo_ivy",  # name of the database
        database_name="eos",  # name of the database
        collection_name="collection",  # name of the collection
        host="10.10.10.31",  # url for the database server
        port="27017",  # port for the database server
        user_name="",  # username for the database server
        password="",  # password for the database server
        proxy="",  # proxy for the database server
        type="RECORD",
    ),
    DBConfig(
        server_name="mongo_dill",  # name of the database
        database_name="eos",  # name of the database
        collection_name="collection",  # name of the collection
        host="10.10.10.23",  # url for the database server
        port="27017",  # port for the database server
        user_name="",  # username for the database server
        password="",  # password for the database server
        proxy="",  # proxy for the database server
        type="RECORD",
    ),
    DBConfig(
        server_name="mongo_intra_sloppy",  # name of the database
        database_name="eos",  # name of the database
        collection_name="collection",  # name of the collection
        host="10.0.64.64",  # url for the database server
        port="30116",  # port for the database server
        user_name="root",  # username for the database server
        password="Newrizon123",  # password for the database server
        proxy="",  # proxy for the database server
        type="RECORD",
    ),
    DBConfig(
        server_name="mongo_cloud",  # name of the database
        database_name="eos",  # name of the database
        collection_name="collection",  # name of the collection
        host="10.10.0.7",  # url for the database server
        port="30116",  # port for the database server
        user_name="",  # username for the database server
        password="",  # password for the database server
        proxy="",  # proxy for the database server
        type="RECORD",
    ),
    DBConfig(
        server_name="mongo_cluster",  # name of the database
        database_name="eos",  # name of the database
        collection_name="collection",  # name of the collection
        host="10.10.0.4",  # url for the database server
        port="23000",  # port for the database server
        user_name="admin",  # username for the database server
        password="ty02ydhVqDj3QFjT",  # password for the database server
        proxy="",  # proxy for the database server
        type="RECORD",
    ),
    DBConfig(
        server_name="mongo_cluster_intra",  # name of the database
        database_name="eos",  # name of the database
        collection_name="collection",  # name of the collection
        host="10.0.48.115",  # url for the database server
        port="23000",  # port for the database server
        user_name="admin",  # username for the database server
        password="ty02ydhVqDj3QFjT",  # password for the database server
        proxy="",  # proxy for the database server
        type="RECORD",
    ),
    DBConfig(
        server_name="hostdb",  # name of the database, in the same bridge network of the docker host
        database_name="eos",  # name of the database
        collection_name="collection",  # name of the collection
        host="hostdb",  # url for the database server
        port="27017",  # port for the database server
        user_name="",  # username for the database server
        password="",  # password for the database server
        proxy="",  # proxy for the database server
        type="RECORD",
    ),
]

# %% ../../nbs/03.config.db.ipynb 8
db_config_servers_by_name = dict(
    zip([db_config.server_name for db_config in db_config_list], db_config_list)
)
db_config_servers_by_host = dict(
    zip([db_config.host for db_config in db_config_list], db_config_list)
)

# %% ../../nbs/03.config.db.ipynb 11
def get_db_config(
    db_key: str,  # string for db server name or format "usr:password@host:port"
) -> DBConfig:  # DBConfig object
    """Get the db config.

    Args:
        db_key (str): string for db server name or format "usr:password@host:port"

    Returns:
        dict: db_config
    """

    # p is the validation pattern for pool_key as mongodb login string "usr:password@host:port"
    login_p = re.compile(RE_DB_KEY)
    assert "mongo" in db_key or login_p.match(db_key), (
        f"Wrong format for db key {db_key}! "
        'It should be either the name of the db server (containing substring "mongo") or '
        'the format "usr:password@host:port"'
    )

    # db_config = DBConfig()
    if "mongo" in db_key.lower():
        db_config = db_config_servers_by_name.get(db_key)
        assert db_config is not None, f"No database found for db_key {db_key}!"
    else:
        # if not given as name then parse the format "usr:password@host:port"
        account_server = [s.split(":") for s in db_key.split("@")]
        flat_account_server = [s for sg in account_server for s in sg]
        assert (len(account_server) == 1 and len(flat_account_server) == 2) or (
            len(account_server) == 2 and len(flat_account_server) == 4
        ), f"Wrong format for db key {db_key}!"
        if len(account_server) == 1:
            db_config = db_config_servers_by_host.get(flat_account_server[0])
            assert (
                db_config is not None and db_config.port == flat_account_server[1]
            ), f"Config mismatch for db key {db_key}!"

        else:
            db_config = db_config_servers_by_host.get(flat_account_server[2])
            assert (
                db_config is not None
                and db_config.port == flat_account_server[3]
                and db_config.user_name == flat_account_server[0]
                and db_config.password == flat_account_server[1]
            ), f"Config mismatch for db server {db_key}!"

    assert type(db_config) is DBConfig, f"Wrong type for db_config {db_config}!"
    return db_config
