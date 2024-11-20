
from public.traits.interface import BASE_USER_NAME, BASE_USER_PASS, ADMIN_USER_NAME, ADMIN_USER_PASS
from traits.implementation import Traits, TraitsUtility
from public.traits.interface import TraitsKey, TrainStatus, SortingCriteria
import pytest
from tests.fixtures import *

# making use of the defined fixtures in tests/fixtures.py and in tests/conftest.py


################################################################################
# Testing the TraitsUtility class
################################################################################

def test_generate_sql_initialization_code(rdbms_connection, rdbms_admin_connection, neo4j_db):
    expected_statements = [
            f"DROP USER IF EXISTS '{ADMIN_USER_NAME}'@'%';",
            f"DROP USER IF EXISTS '{BASE_USER_NAME}'@'%';",
            f"CREATE USER '{ADMIN_USER_NAME}'@'%' IDENTIFIED BY '{ADMIN_USER_PASS}';",
            f"CREATE USER '{BASE_USER_NAME}'@'%' IDENTIFIED BY '{BASE_USER_PASS}';",
            f"GRANT ALL PRIVILEGES ON *.* TO '{ADMIN_USER_NAME}'@'%';",  # all privileges for the admin user
            f"GRANT SELECT, INSERT, UPDATE ON *.* TO '{BASE_USER_NAME}'@'%';",  # only SELECT and INSERT (buying tickets) for the base user

            """
            CREATE TABLE IF NOT EXISTS Users (
                email VARCHAR(255) UNIQUE NOT NULL PRIMARY KEY, 
                user_details VARCHAR(255)
                CHECK (email REGEXP '^[^@]+@[^@]+\\.[^@]+$')
                );
            """,  # user_details can be NULL
            """
            CREATE TABLE IF NOT EXISTS Trains (
                train_id INT AUTO_INCREMENT PRIMARY KEY,
                capacity INT NOT NULL,
                status INT NOT NULL DEFAULT 0,
                CHECK (status IN (0, 1, 2))
            );
            """,  # 0 operational, 1 delayed, 2 broken
            """
            CREATE TABLE IF NOT EXISTS Tickets (
                ticket_id INT AUTO_INCREMENT PRIMARY KEY,
                user_email VARCHAR(255) NOT NULL,
                train_id INT NOT NULL,
                purchase_date DATETIME NOT NULL,
                reserved_seat BIT NOT NULL DEFAULT 0,
                price FLOAT NOT NULL,
                start_station_key INT NOT NULL,
                end_station_key INT NOT NULL,
                FOREIGN KEY (user_email) REFERENCES Users(email),
                FOREIGN KEY (train_id) REFERENCES Trains(train_id)
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS PurchaseHistory (
                user_email VARCHAR(255) NOT NULL,
                ticket_id INT NOT NULL,
                purchase_date DATETIME NOT NULL,
                FOREIGN KEY (user_email) REFERENCES Users(email),
                FOREIGN KEY (ticket_id) REFERENCES Tickets(ticket_id),
                PRIMARY KEY (user_email, ticket_id)
                );
            """
        ]
    # create the database
    actual_statements = TraitsUtility.generate_sql_initialization_code()

    assert len(expected_statements) == len(actual_statements)  # The number of SQL statements should match

def test_get_all_users(rdbms_connection, rdbms_admin_connection, neo4j_db):
    # Create an instance of the TraitsUtility class and the Traits class (basic setup, through tests)
    utils = TraitsUtility(rdbms_connection, rdbms_admin_connection, neo4j_db)
    t = Traits(rdbms_connection, rdbms_admin_connection, neo4j_db)

    # Check if the database is empty
    assert len(utils.get_all_users()) == 0, f"Databse should be empty, but it contains {len(utils.get_all_users())} users"

    # Add a user to the database
    user_email = "testuser@email.org"
    user_details = None
    t.add_user(user_email, user_details)

    # Check if the added user is in the returned list
    assert len(utils.get_all_users()) == 1, f"User {user_email} not inserted"


def test_get_all_schedules(rdbms_connection, rdbms_admin_connection, neo4j_db, setup_train, setup_station_connections):
    utils = TraitsUtility(rdbms_connection, rdbms_admin_connection, neo4j_db)
    t = Traits(rdbms_connection, rdbms_admin_connection, neo4j_db)

    # Check if the database is empty
    assert len(utils.get_all_schedules()) == 0, f"Database should be empty, but it contains {len(utils.get_all_schedules())} schedules"

    # Add a schedule to the database
    train_key = setup_train  # Use the train_key from the fixture
    starting_hours_24_h = 10
    starting_minutes = 30
    stops = [(setup_station_connections[0], 0), (setup_station_connections[1], 10)]  # Use the station_keys from the fixture
    valid_from_day = 1
    valid_from_month = 1
    valid_from_year = 2022
    valid_until_day = 31
    valid_until_month = 12
    valid_until_year = 2022
    t.add_schedule(train_key, starting_hours_24_h, starting_minutes, stops, valid_from_day, valid_from_month, valid_from_year, valid_until_day, valid_until_month, valid_until_year)

    # Check if the added schedule is in the returned list
    assert len(utils.get_all_schedules()) == 1, f"Schedule not inserted"


################################################################################
# Testing the Traits class
################################################################################

    # Basic Features
    #######################################
def test_search_connections(rdbms_connection, rdbms_admin_connection, neo4j_db, setup_stations, setup_station_connections):
    t = Traits(rdbms_connection, rdbms_admin_connection, neo4j_db)

    # Define the starting and ending stations
    starting_station_key = setup_stations[0]
    ending_station_key = setup_stations[-1]  # Assuming the last station is connected to the first

    # Call the search_connections method
    connections = t.search_connections(starting_station_key, ending_station_key)

    # Check that the returned list is not empty
    assert len(connections) > 0, "No connections found"

    # Check that the first and last stations in the returned connections match the input stations
    assert str(connections[0]['start_key']) == starting_station_key.to_string(), "Starting station does not match"
    assert str(connections[-1]['end_key']) == ending_station_key.to_string(), "Ending station does not match"


def test_search_connections_sorting(rdbms_connection, rdbms_admin_connection, neo4j_db, setup_stations, setup_station_connections):
    t = Traits(rdbms_connection, rdbms_admin_connection, neo4j_db)

    # Define the starting and ending stations
    starting_station_key = setup_stations[0]
    ending_station_key = setup_stations[-1]  # Assuming the last station is connected to the first

    # Call the search_connections method with different sorting criteria
    # Loop through all the sorting criteria:
    for sorting_criteria in SortingCriteria:
        connections = t.search_connections(starting_station_key, ending_station_key, sort_by=sorting_criteria)

        # Check that the returned list is not empty
        assert len(connections) > 0, "No connections found"

        # Check that the connections are sorted correctly
        # Create a sorted copy of the connections list based on the sorting criteria
        if sorting_criteria == SortingCriteria.OVERALL_TRAVEL_TIME:
            sorted_connections = sorted(connections, key=lambda x: x['travel_time'])
        elif sorting_criteria == SortingCriteria.NUMBER_OF_TRAIN_CHANGES:
            sorted_connections = sorted(connections, key=lambda x: x['changes'])
        elif sorting_criteria == SortingCriteria.OVERALL_WAITING_TIME:
            connections = [conn for conn in connections if conn['waiting_time'] is not None]
            sorted_connections = sorted(connections, key=lambda x: x['waiting_time'])
        elif sorting_criteria == SortingCriteria.ESTIMATED_PRICE:
            sorted_connections = sorted(connections, key=lambda x: x['estimated_price'])

        # Check that the connections list is equal to its sorted copy
        assert connections == sorted_connections, "Connections are not sorted correctly"

def test_get_train_current_status(rdbms_connection, rdbms_admin_connection, neo4j_db, setup_train):
    t = Traits(rdbms_connection, rdbms_admin_connection, neo4j_db)

    # train_key from the setup_train fixture
    train_key = setup_train

    # Call the method
    status = t.get_train_current_status(train_key)

    # Check that the returned status is not None (because the train exists)
    assert status is not None, "Status should not be None for existing train"

    # testing a non-existent train_key
    non_existent_train_key = TraitsKey(9999)  # Assuming 9999 is not a valid train_id in the database
    status = t.get_train_current_status(non_existent_train_key)

    # Check that the returned status is None (because the train does not exist)
    assert status is None, "Status should be None for non-existent train"


def test_get_train_current_status_non_existent_train(rdbms_connection, rdbms_admin_connection, neo4j_db):
    t = Traits(rdbms_connection, rdbms_admin_connection, neo4j_db)

    # Use a non-existent train_key
    non_existent_train_key = TraitsKey(9999)  # Assuming 9999 is not a valid train_id in the database

    # Call the get_train_current_status method
    status = t.get_train_current_status(non_existent_train_key)

    # Check that the returned status is None
    assert status is None, "Status should be None for non-existent train"

    ##################################
    # Advanced Features
    ##################################


def test_buy_ticket_with_seat_reservation(rdbms_connection, rdbms_admin_connection, neo4j_db, setup_user, setup_train, setup_connection):
    t = Traits(rdbms_connection, rdbms_admin_connection, neo4j_db)

    # Use the user_email from the fixtures
    user_email = setup_user

    # Use the train_id from the setup_train fixture
    train_id = setup_train.to_int()  # Assuming setup_train is a TraitsKey object

    # get original capacity
    with rdbms_connection.cursor(dictionary=True) as cursor:  # using the user connection to not interfere with the function
        cursor.execute("SELECT * FROM Trains WHERE train_id = %s", (train_id,))
        initial_capacity = cursor.fetchone()['capacity']

    # Create a list of connections (as dictionaries) for testing purposes
    connection = setup_connection

    also_reserve_seats = True  # Reserve seats

    # Call the buy_ticket method
    t.buy_ticket(user_email, connection, also_reserve_seats)

    # Check that the total price was correctly calculated and the train's capacity was updated
    with rdbms_connection.cursor(dictionary=True) as cursor:  # Using a DictCursor to get the results as dictionaries
        # Get the ticket
        cursor.execute("SELECT * FROM Tickets WHERE user_email = %s AND train_id = %s", (user_email, train_id))
        ticket = cursor.fetchone()
        assert ticket is not None, "Ticket was not created"
        assert ticket['price'] == round(sum(c['travel_time'] for c in connection) / 2 + len(connection) * 2, 2), "Total price was not correctly calculated"

        # Get the train and check its capacity
        cursor.execute("SELECT * FROM Trains WHERE train_id = %s", (train_id,))
        train = cursor.fetchone()
        assert train['capacity'] == initial_capacity - 1, "Train's capacity was not correctly updated"


def test_get_purchase_history(rdbms_connection, rdbms_admin_connection, neo4j_db, setup_user, setup_connection):
    t = Traits(rdbms_connection, rdbms_admin_connection, neo4j_db)

    # Buy a ticket, so that there is a purchase history
    user_email = setup_user
    setup_user = user_email
    setup_connection = setup_connection
    also_reserve_seats = True
    t.buy_ticket(setup_user, setup_connection, also_reserve_seats)

    # Call the get_purchase_history method
    purchase_history = t.get_purchase_history(user_email)

    # Check that the returned list is not empty
    assert len(purchase_history) > 0, "No purchase history found for registered user"

    # Use a non-registered user's email
    non_registered_user_email = "non_registered_user@example.com"

    # Call the get_purchase_history method with the non-registered user's email
    purchase_history = t.get_purchase_history(non_registered_user_email)

    # Check that the returned list is empty
    assert len(purchase_history) == 0, "Purchase history found for non-registered user"


    ########################################################################
    # Admin Features:
    ########################################################################


def test_add_user(rdbms_connection, rdbms_admin_connection, neo4j_db):
    t = Traits(rdbms_connection, rdbms_admin_connection, neo4j_db)

    # Test adding a new user
    new_user_email = "new_user@example.com"
    user_details = "User Details"
    t.add_user(new_user_email, user_details)

    # Verify that the new user was added
    with rdbms_admin_connection.cursor(dictionary=True) as cursor:  # Using a DictCursor to get the results as dictionaries
        cursor.execute("SELECT * FROM Users WHERE email = %s;", (new_user_email,))
        user = cursor.fetchone()
        assert user is not None, "User was not added"
        assert user['user_details'] == user_details, "User details do not match"

    # Test adding a user with an existing email
    with pytest.raises(ValueError) as exc_info:
        t.add_user(new_user_email, user_details)

    # Test adding a user with an invalid email format
    with pytest.raises(ValueError) as exc_info:
        t.add_user("invalid_email_format", user_details)


def test_delete_non_existent_user(rdbms_connection, rdbms_admin_connection, neo4j_db):
    t = Traits(rdbms_connection, rdbms_admin_connection, neo4j_db)

    # Try to delete a user that does not exist
    non_existent_user_email = "nonexistentuser@email.org"

    with pytest.raises(ValueError) as exc_info:
        t.delete_user(non_existent_user_email)


def test_add_train(rdbms_connection, rdbms_admin_connection, neo4j_db):
    t = Traits(rdbms_connection, rdbms_admin_connection, neo4j_db)

    # Test adding a new train
    new_train_key = TraitsKey(1)
    train_capacity = 100
    train_status = TrainStatus.OPERATIONAL
    t.add_train(new_train_key, train_capacity, train_status)

    # Verify that the new train was added
    with rdbms_admin_connection.cursor(dictionary=True) as cursor:
        cursor.execute("SELECT * FROM Trains WHERE train_id = %s;", (new_train_key.to_int(),))
        train = cursor.fetchone()
        assert train is not None, "Train was not added"
        assert train['capacity'] == train_capacity, "Train capacity does not match"
        assert train['status'] == train_status.value, "Train status does not match"

    # Test adding a train with an existing key
    with pytest.raises(ValueError) as exc_info:
        t.add_train(new_train_key, train_capacity, train_status)


def test_update_non_existent_train_details(rdbms_connection, rdbms_admin_connection, neo4j_db):
    t = Traits(rdbms_connection, rdbms_admin_connection, neo4j_db)

    # Use a non-existent train_key
    non_existent_train_key = TraitsKey(9999)  # Assuming 9999 is not a valid train_id in the database
    train_capacity = 100
    train_status = TrainStatus.OPERATIONAL

    # Try to update the details of a train that does not exist
    with pytest.raises(ValueError) as exc_info:
        t.update_train_details(non_existent_train_key, train_capacity, train_status)


def test_update_train_details_with_lower_capacity(rdbms_connection, rdbms_admin_connection, neo4j_db, setup_train):
    t = Traits(rdbms_connection, rdbms_admin_connection, neo4j_db)

    # Use the train_key from the setup_train fixture
    train_key = setup_train

    # Get the current capacity of the train
    with rdbms_admin_connection.cursor(dictionary=True) as cursor:
        cursor.execute("SELECT * FROM Trains WHERE train_id = %s", (train_key.to_int(),))
        train = cursor.fetchone()
        current_capacity = train['capacity']

    # Try to update the train's capacity to a lower value
    lower_capacity = current_capacity - 1

    with pytest.raises(ValueError) as exc_info:
        t.update_train_details(train_key, lower_capacity)


def test_update_train_details_with_broken_status(rdbms_connection, rdbms_admin_connection, neo4j_db, setup_train):
    t = Traits(rdbms_connection, rdbms_admin_connection, neo4j_db)

    # Use the train_key from the setup_train fixture
    train_key = setup_train

    # Update the train's status to BROKEN
    t.update_train_details(train_key, train_status=TrainStatus.BROKEN)

    # Verify that the train's status was updated
    with rdbms_admin_connection.cursor(dictionary=True) as cursor:
        cursor.execute("SELECT * FROM Trains WHERE train_id = %s;", (train_key.to_int(),))
        train = cursor.fetchone()
        assert train['status'] == TrainStatus.BROKEN.value, "Train status was not updated to BROKEN"

    # Verify that all reservations for the train were cancelled
    with rdbms_admin_connection.cursor() as cursor:
        cursor.execute("SELECT * FROM Tickets WHERE train_id = %s AND reserved_seat = TRUE;", (train_key.to_int(),))
        reserved_tickets = cursor.fetchall()
        assert len(reserved_tickets) == 0, "Not all reservations were cancelled"


def test_delete_train(rdbms_connection, rdbms_admin_connection, neo4j_db, setup_train):
    t = Traits(rdbms_connection, rdbms_admin_connection, neo4j_db)

    # train_key from the setup_train fixture
    train_key = setup_train

    # Call the delete_train method
    t.delete_train(train_key)

    # Verify that the train was deleted from the Trains table
    with rdbms_admin_connection.cursor() as cursor:
        cursor.execute("SELECT * FROM Trains WHERE train_id = %s;", (train_key.to_int(),))
        train = cursor.fetchone()
        assert train is None, "Train was not deleted"

    # Verify that the train's tickets were deleted from the Tickets table
    with rdbms_admin_connection.cursor() as cursor:
        cursor.execute("SELECT * FROM Tickets WHERE train_id = %s;", (train_key.to_int(),))
        tickets = cursor.fetchall()
        assert len(tickets) == 0, "Train's tickets were not deleted"

    # Verify that the train's schedules were deleted from the Neo4j database
    with neo4j_db.session() as session:
        result = session.run("MATCH (t:Train {id: $train_id})-[r:SCHEDULE]->() RETURN r", train_id=train_key.to_string())
        schedules = result.data()
        assert len(schedules) == 0, "Train's schedules were not deleted"


def test_add_train_station(rdbms_connection, rdbms_admin_connection, neo4j_db):
    t = Traits(rdbms_connection, rdbms_admin_connection, neo4j_db)

    # Test adding a new station
    new_station_key = TraitsKey(1)
    station_details = "New Station Details"
    t.add_train_station(new_station_key, station_details)

    # Verify that the new station was added
    with neo4j_db.session() as session:
        result = session.run("MATCH (s:Station {station_id: $station_id}) RETURN s", station_id=new_station_key.to_int())
        station = result.single()
        assert station is not None, "Station was not added"
        # check if the details are correct
        result = session.run("MATCH (s:Station {station_id: $station_id}) RETURN s.details", station_id=new_station_key.to_int())
        details = result.single()
        assert details[0] == station_details, "Station details do not match"

    # Test adding a station with an existing key
    with pytest.raises(ValueError) as exc_info:
        t.add_train_station(new_station_key, station_details)


def test_connect_already_connected_train_stations(neo4j_db, rdbms_connection, rdbms_admin_connection):
    t = Traits(rdbms_connection, rdbms_admin_connection, neo4j_db)

    # Add two train stations to the database
    starting_train_station_key = TraitsKey(1)
    train_station_details = None
    t.add_train_station(starting_train_station_key, train_station_details)

    ending_train_station_key = TraitsKey(2)
    t.add_train_station(ending_train_station_key, train_station_details)

    # Connect the two train stations
    travel_time_in_minutes = 20
    t.connect_train_stations(starting_train_station_key, ending_train_station_key, travel_time_in_minutes)

    # Try to connect the same two train stations again
    with pytest.raises(ValueError) as exc_info:
        t.connect_train_stations(starting_train_station_key, ending_train_station_key, travel_time_in_minutes)


def test_add_schedule_with_invalid_parameters(rdbms_connection, rdbms_admin_connection, neo4j_db, setup_train):
    t = Traits(rdbms_connection, rdbms_admin_connection, neo4j_db)

    # Use the train_key from the setup_train fixture
    train_key = setup_train

    # Some valid parameters
    starting_hours_24_h = 10
    starting_minutes = 30
    stops = [(TraitsKey(1), 0), (TraitsKey(2), 10)]
    valid_from_day = 1
    valid_from_month = 1
    valid_from_year = 2022
    valid_until_day = 31
    valid_until_month = 12
    valid_until_year = 2022

    # Test with train_key as None
    with pytest.raises(ValueError) as exc_info:
        t.add_schedule(None, starting_hours_24_h, starting_minutes, stops, valid_from_day, valid_from_month, valid_from_year, valid_until_day, valid_until_month, valid_until_year)
    # Check the error message is the expected one
    assert str(exc_info.value) == "train_key cannot be None", "Wrong error message"

    # Test with less than two stops
    with pytest.raises(ValueError) as exc_info:
        t.add_schedule(train_key, starting_hours_24_h, starting_minutes, [(TraitsKey(1), 0)], valid_from_day, valid_from_month, valid_from_year, valid_until_day, valid_until_month, valid_until_year)
    assert str(exc_info.value) == "The schedule must have at least two stops", "Wrong error message"

    # Test with valid_from in the future w.r.t. valid_until
    with pytest.raises(ValueError) as exc_info:
        t.add_schedule(train_key, starting_hours_24_h, starting_minutes, stops, valid_until_day, valid_until_month, valid_until_year, valid_from_day, valid_from_month, valid_from_year)
    assert str(exc_info.value) == "Validity dates must ensure that valid_from is in the past w.r.t. valid_until", "Wrong error message"

    # Test with non-existent train
    non_existent_train_key = TraitsKey(9999)  # Assuming 9999 is not a valid train_id in the database
    with pytest.raises(ValueError) as exc_info:
        t.add_schedule(non_existent_train_key, starting_hours_24_h, starting_minutes, stops, valid_from_day, valid_from_month, valid_from_year, valid_until_day, valid_until_month, valid_until_year)
    assert str(exc_info.value) == "Train does not exist", "Wrong error message"

    # Test with non-existent stations
    non_existent_station_key = TraitsKey(9999)  # Assuming 9999 is not a valid station_id in the database
    stops_with_non_existent_station = [(non_existent_station_key, 0), (TraitsKey(2), 10)]
    with pytest.raises(ValueError) as exc_info:
        t.add_schedule(train_key, starting_hours_24_h, starting_minutes, stops_with_non_existent_station, valid_from_day, valid_from_month, valid_from_year, valid_until_day, valid_until_month, valid_until_year)
    assert str(exc_info.value) == "One or both stations do not exist", "Wrong error message"

    # Test with unconnected consecutive stops done in public tests
