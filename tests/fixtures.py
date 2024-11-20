import datetime

from public.traits.interface import BASE_USER_NAME, BASE_USER_PASS, ADMIN_USER_NAME, ADMIN_USER_PASS
from traits.implementation import Traits, TraitsUtility
from public.traits.interface import TraitsKey, TrainStatus, SortingCriteria
import pytest


@pytest.fixture
def setup_train(rdbms_connection, rdbms_admin_connection, neo4j_db):
    t = Traits(rdbms_connection, rdbms_admin_connection, neo4j_db)
    train_key = TraitsKey(1)
    train_capacity = 100
    t.add_train(train_key, train_capacity, train_status=TrainStatus.OPERATIONAL)
    return train_key

@pytest.fixture
def setup_stations(rdbms_connection, rdbms_admin_connection, neo4j_db):
    t = Traits(rdbms_connection, rdbms_admin_connection, neo4j_db)
    # Add the stations
    station_keys = [TraitsKey(1), TraitsKey(2), TraitsKey(3)]
    for station_key in station_keys:
        t.add_train_station(station_key, None)
    return station_keys

@pytest.fixture
def setup_station_connections(rdbms_connection, rdbms_admin_connection, neo4j_db, setup_stations):
    t = Traits(rdbms_connection, rdbms_admin_connection, neo4j_db)
    # Connect the stations
    for i in range(len(setup_stations) - 1):
        t.connect_train_stations(setup_stations[i], setup_stations[i + 1], 30)
    return setup_stations


@pytest.fixture
def setup_connection(setup_train, setup_stations):  # for test_buy_ticket
    # Define the connections for testing purposes
    train_id = setup_train.to_int()  # Call the setup_train fixture to get the train_id
    connections = [
        {
            'train_id': train_id,  # Use the train_id from the setup_train fixture
            'starting_station_key': setup_stations[0].to_int(),  # Use the key from the setup_stations fixture
            'ending_station_key': setup_stations[1].to_int(),  # Use the key from the setup_stations fixture
            'travel_time': 20
        },
        {
            'train_id': train_id,  # Use the same train_id for the second connection
            'starting_station_key': setup_stations[1].to_int(),  # Use the key from the setup_stations fixture
            'ending_station_key': setup_stations[2].to_int(),  # Use the key from the setup_stations fixture
            'travel_time': 30
        }
        # Add more connections as needed
    ]
    return connections

@pytest.fixture
def setup_user(rdbms_admin_connection):
    # Create a user for testing purposes
    user_email = "testuser@email.org"
    user_details = None

    with rdbms_admin_connection.cursor() as cursor:
        cursor.execute("INSERT INTO Users (email, user_details) VALUES (%s, %s)", (user_email, user_details))

    return user_email

@pytest.fixture
def setup_purchase_history(rdbms_admin_connection, setup_user, setup_train):
    # Create a purchase history for testing purposes
    user_email = setup_user
    train_id = setup_train.to_int()
    reserved_seat = True
    price = 20.0
    purchase_date = datetime.datetime.now()
    start_station_key = 1
    end_station_key = 2

    with rdbms_admin_connection.cursor() as cursor:
        cursor.execute("INSERT INTO Tickets (user_email, train_id, reserved_seat, price, purchase_date, start_station_key, end_station_key) VALUES (%s, %s, %s, %s, %s, %s, %s)", (user_email, train_id, reserved_seat, price, purchase_date, start_station_key, end_station_key))
        ticket_id = cursor.lastrowid
        cursor.execute("INSERT INTO PurchaseHistory (user_email, ticket_id, purchase_date) VALUES (%s, %s, %s)", (user_email, ticket_id, purchase_date))

    return user_email

