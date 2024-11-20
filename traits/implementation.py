from datetime import datetime, timedelta

# from neo4j import GraphDatabase
from typing import List, Optional, Tuple

# import all the necessary classes from the public submodule:
from public.traits.interface import TraitsInterface, TraitsUtilityInterface, TraitsKey, TrainStatus, SortingCriteria

# import all the necessary default configurations
from public.traits.interface import BASE_USER_NAME, BASE_USER_PASS, ADMIN_USER_NAME, ADMIN_USER_PASS


# implement the utility class (any additional methods needed can be added)
class TraitsUtility(TraitsUtilityInterface):
    def __init__(self, rdbms_connection, rdbms_admin_connection, neo4j_driver) -> None:
        self.rdbms_connection = rdbms_connection
        self.rdbms_admin_connection = rdbms_admin_connection
        self.neo4j_driver = neo4j_driver

    @staticmethod
    def generate_sql_initialization_code() -> List[str]:

        # this code ensures that users are recreated as needed.
        # proper permissions and statements to setup the database should be added.

        return [
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

    def get_all_users(self) -> List:
        """
        Return all the users stored in the database
        """
        # using with statement to automatically close the cursor when done
        with self.rdbms_admin_connection.cursor() as cursor:  # admin features
            cursor.execute("SELECT * FROM Users;")
            users = cursor.fetchall()
            return users

    def get_all_schedules(self) -> List:
        """
        Return all the schedules stored in the database
        """
        with self.neo4j_driver.session() as session:  # automatically closes the session
            result = session.run("MATCH (n:Schedule) RETURN n")  # get all schedules
            return result.data()


# implementing the main class we need to implement
class Traits(TraitsInterface):

    def __init__(self, rdbms_connection, rdbms_admin_connection, neo4j_driver) -> None:
        self.rdbms_connection = rdbms_connection
        self.rdbms_admin_connection = rdbms_admin_connection
        self.neo4j_driver = neo4j_driver

    ########################################################################
    # Basic Features
    ########################################################################

    def search_connections(self, starting_station_key: TraitsKey, ending_station_key: TraitsKey,
                           travel_time_day: int = None, travel_time_month: int = None, travel_time_year: int = None,
                           is_departure_time=True,
                           sort_by: SortingCriteria = SortingCriteria.OVERALL_TRAVEL_TIME, is_ascending: bool = True,
                           limit: int = 5) -> List:
        """
        Search Train Connections (between two stations).
        Sorting criteria can be one of the following:overall travel time, number of train changes, waiting time, and estimated price

        Return the connections from a starting and ending stations, possibly including changes at interchanging stations.
        Returns an empty list if no connections are possible
        Raise a ValueError in case of errors and if the starting or ending stations are the same
        """

        # Check if the starting and ending stations are the same
        if starting_station_key.to_string() == ending_station_key.to_string():
            raise ValueError("Starting and ending stations cannot be the same")

        # Check if the starting and ending stations exist
        with self.neo4j_driver.session() as session:
            result_start = session.run("MATCH (s:Station {station_id: $station_id}) RETURN s",
                                       station_id=starting_station_key.to_int())
            result_end = session.run("MATCH (s:Station {station_id: $station_id}) RETURN s",
                                     station_id=ending_station_key.to_int())
            if result_start.single() is None or result_end.single() is None:
                raise ValueError("One or both stations do not exist")

        # If a travel date is provided, convert it to a datetime object
        travel_date = None
        if travel_time_day and travel_time_month and travel_time_year:
            travel_date = datetime(travel_time_year, travel_time_month, travel_time_day)

        # Define the sorting criteria (using list comprehension in neo4j to avoid multiple ORDER BY statements)
        sorting = "reduce(time = 0, x in connection | time + x.travel_time)"  # default to overall travel time (sum of travel times)
        if sort_by == SortingCriteria.NUMBER_OF_TRAIN_CHANGES:
            sorting = "size(connection) - 1 "  # number of train changes (number of connections - 1)
        elif sort_by == SortingCriteria.OVERALL_WAITING_TIME:
            sorting = "reduce(time = 0, x in range(1, size(connection)) | time + (connection[x].departure_time - connection[x-1].arrival_time))"  # overall waiting time (difference between arrival and departure times)
        elif sort_by == SortingCriteria.ESTIMATED_PRICE:
            sorting = "reduce(price = 0, x in connection | price + x.price)"  # estimated price (sum of prices)

        # Build the query
        #  finds all possible paths between the starting and ending stations and calculates the overall travel time, number of train changes, waiting time, and estimated price
        query = f"""
            MATCH path=(start:Station {{station_id: $start_id}})-[connection:CONNECTION*]->(end:Station {{station_id: $end_id}})
            WHERE 1=1 {f" AND connection.date = '{travel_date.strftime('%Y-%m-%dT%H:%M')}'" if travel_date else ""}
            WITH path, connection, start, end
            RETURN start.station_id AS start_key, end.station_id AS end_key, reduce(price = 0, r in connection | price + r.price) AS estimated_price, reduce(time = 0, x in connection | time + x.travel_time) AS travel_time, size(connection) - 1 AS changes, reduce(time = 0, x in range(1, size(connection)) | time + (connection[x].departure_time - connection[x-1].arrival_time)) AS waiting_time
            ORDER BY {sorting} {"ASC" if is_ascending else "DESC"}
            LIMIT $limit
        """

        # Run the query and return the result (empty list if no connections are possible)
        with self.neo4j_driver.session() as session:
            result = session.run(query, start_id=starting_station_key.to_int(), end_id=ending_station_key.to_int(), limit=limit)
            return result.data()

    def get_train_current_status(self, train_key: TraitsKey) -> Optional[TrainStatus]:
        """
        Check the status of a train. If the train does not exist returns None
        """
        with self.rdbms_admin_connection.cursor() as cursor:  # using admin connection on purpose, as this is an admin feature (and tests would fail without it)
            cursor.execute("SELECT status FROM Trains WHERE train_id = %s;", (train_key.to_int(),))  # %s is a placeholder
            status = cursor.fetchone()

            if status is None:  # train does not exist
                return None
            return TrainStatus(status[0])  # 0 operational, 1 delayed, 2 broken (status[0] because status is a tuple)

    ########################################################################
    # Advanced Features
    ########################################################################

    def buy_ticket(self, user_email: str, connection, also_reserve_seats=True):
        """
        Given a train connection instance (e.g., on a given date/time), registered users can book tickets and optionally reserve seats. When the user decides to reserve seats, the system will try to reserve all the available seats automatically.
        We make the following assumptions:
            - There is always a place on the trains, so tickets can be always bought
            - The train seats are not numbered, so the system must handle only the number of passengers booked on a train and not each single seat.
            - The system grants only those seats that are effectively available at the moment of request; thus, overbooking on reserved seats is not possible.
            - Seats reservation cannot be done after booking a ticket.
            - A user can only reserve one seat in each train at the given time.

        If the user does not exist, the method must raise a ValueError
        """

        # Check if the user exists (is registered)
        with self.rdbms_connection.cursor(dictionary=True) as cursor:  # dictionary=True to get the results as dictionaries
            cursor.execute("SELECT * FROM Users WHERE email = %s", (user_email,))
            user = cursor.fetchone()
            if user is None:
                raise ValueError("User does not exist")

            # get connection details:
            # looping through the connections to calculate the total price and reserve seats
            distance_price = 0
            # assuming that the connection is a list of dictionaries with the following keys: train_id, starting_station_key, ending_station_key, travel_time
            for c in connection:
                # Check if the train exists
                train_id = c['train_id']
                cursor.execute("SELECT * FROM Trains WHERE train_id = %s", (train_id,))
                train = cursor.fetchone()
                if train is None:
                    raise ValueError("Train does not exist")

                # Check if the train has enough capacity if the user wants to reserve a seat
                if train['capacity'] <= 0 and also_reserve_seats:  # no seats available, but user wants to reserve
                    raise ValueError("No seats available for reservation")

                # Calculate the travel price
                distance_price += c['travel_time']   # summing up the travel time

            total_price = round(distance_price / 2, 2)  # price per minute
            if also_reserve_seats:
                total_price += len(connection) * 2  # 2 euros per reserved seat

            # Insert a new row into the Tickets table
            cursor.execute("INSERT INTO Tickets (user_email, train_id, reserved_seat, price, purchase_date, start_station_key, end_station_key ) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                           (user_email, train_id, also_reserve_seats, total_price, datetime.now().isoformat(), connection[0]['starting_station_key'], connection[-1]['ending_station_key']))

            # Get the ticket_id of the newly inserted ticket
            ticket_id = cursor.lastrowid

            # Insert a new row into the PurchaseHistory table
            cursor.execute("INSERT INTO PurchaseHistory (user_email, ticket_id, purchase_date) VALUES (%s, %s, %s)",
                           (user_email, ticket_id, datetime.now().isoformat()))

            # If also_reserve_seats is True, decrement the train's capacity by 1
            if also_reserve_seats:
                cursor.execute("UPDATE Trains SET capacity = capacity - 1 WHERE train_id = %s", (train_id,))

            # Commit the changes
            self.rdbms_connection.commit()

    def get_purchase_history(self, user_email: str) -> List:
        """
        Access Purchase History

        Registered users can list the history of their past purchases, including the starting and ending stations, the day/time, total price, and for each connection, the price and whether they reserved a seat.
        The purchase history is always represented in descending starting time (at the top the most recent trips).

        If the user is not registered, the list is empty
        """

        query = f"""
        SELECT ph.purchase_date, t.price, t.reserved_seat, tr.status, t.start_station_key, t.end_station_key
        FROM Users u
        JOIN PurchaseHistory ph ON u.email = ph.user_email
        JOIN Tickets t ON ph.ticket_id = t.ticket_id
        JOIN Trains tr ON t.train_id = tr.train_id
        WHERE u.email = %s
        ORDER BY ph.purchase_date DESC
        """  # DESC: most recent trips at the top

        # empty list if the user is not registered
        with self.rdbms_connection.cursor() as cursor:  # user connection (only read)
            cursor.execute(query, (user_email,))
            history = cursor.fetchall()
            return history

    ########################################################################
    # Admin Features:
    ########################################################################
    # using only the admin connection for these features
    # Add and remove users

    def add_user(self, user_email: str, user_details) -> None:
        """
        Add a new user to the system with given email and details.
        Email format: <Recipient name>@<Domain name><top-level domain>
        See: https://knowledge.validity.com/s/articles/What-are-the-rules-for-email-address-syntax?language=en_US

        Raise a ValueError if the email has invalid format.
        Raise a ValueError if the user already exists
        """

        with self.rdbms_admin_connection.cursor() as cursor:  # admin connection (read/write)
            # in case no user details are provided
            if user_details is None:
                user_details = "NULL"

            try:
                # add the new user to the Users table (if user does not exist)
                cursor.execute("INSERT INTO Users (email, user_details) VALUES (%s, %s);", (user_email, user_details))
            except:
                # if the email is not in a valid format (CHECK failed) or already exists (UNIQUE constraint failed)
                # the user already exists (UNIQUE constraint failed)
                raise ValueError("Invalid email format or user already exists")

            self.rdbms_admin_connection.commit()

    def delete_user(self, user_email: str) -> None:
        """
        Delete the user from the db if the user exists.
        The method should also delete any data related to the user (past/future tickets and seat reservations)
        """
        with self.rdbms_admin_connection.cursor() as cursor:  # admin connection (read/write)

            # Check if the user exists
            cursor.execute("SELECT * FROM Users WHERE email = %s", (user_email,))
            user = cursor.fetchone()
            if user is None:
                raise ValueError("User does not exist")

            # Find reserved tickets for the user
            cursor.execute("""
                SELECT train_id FROM Tickets 
                WHERE user_email = %s AND reserved_seat = TRUE
            """, (user_email,))
            reserved_tickets = cursor.fetchall()

            # Increment train capacity for each reserved ticket
            for (train_id,) in reserved_tickets:
                cursor.execute("""
                    UPDATE Trains SET capacity = capacity + 1 
                    WHERE id = %s
                """, (train_id,))

            # Delete user's tickets
            cursor.execute("DELETE FROM Tickets WHERE user_email = %s", (user_email,))

            # Delete user's purchase history
            cursor.execute("DELETE FROM PurchaseHistory WHERE user_email = %s", (user_email,))

            # Delete the user
            cursor.execute("DELETE FROM Users WHERE email = %s", (user_email,))

            # Commit the changes and close the cursor
            self.rdbms_admin_connection.commit()

    # Deleting a train should ensure consistency! Reservations are cancelled, schedules/trips are cancelled, etc.
    def add_train(self, train_key: TraitsKey, train_capacity: int, train_status: TrainStatus) -> None:
        """
        Add new trains to the system with given code.

        Raise a ValueError if the train already exists
        """
        with self.rdbms_admin_connection.cursor() as cursor:  # admin connection (read/write)

            # If train_key is None, generate a new one
            if train_key is None:
                cursor.execute("""
                           INSERT INTO Trains (capacity, status)
                           VALUES (%s, %s);
                       """, (train_capacity, train_status.value))  # value: 0 operational, 1 delayed, 2 broken
                self.rdbms_admin_connection.commit()

                # Get the ID of the newly inserted train
                train_id = cursor.lastrowid

                return TraitsKey(train_id)


            # add the new train to the Trains table
            try:
                cursor.execute(f"""
                     INSERT INTO Trains (train_id, capacity, status)
                     VALUES (%s, %s, %s);
                 """, (train_key.to_int(), train_capacity, train_status.value))
            except:
                # if the train already exists (UNIQUE constraint failed)
                # the train status is not valid (CHECK failed)
                raise ValueError("Invalid input or train already exists")
            self.rdbms_admin_connection.commit()

            return train_key  # Return the train_key of the newly created train


    def update_train_details(self, train_key: TraitsKey, train_capacity: Optional[int] = None,
                             train_status: Optional[TrainStatus] = None) -> None:
        """
        Update the details of existing train if specified (i.e., not None), otherwise do nothing.
        """

        with self.rdbms_admin_connection.cursor(dictionary=True) as cursor:
            cursor.execute("SELECT * FROM Trains WHERE train_id = %s;", (train_key.to_int(),))
            train = cursor.fetchone()
            if train is None:
                raise ValueError("Train does not exist")

            if train_capacity is not None:
                # requirement:
                if train_capacity < train['capacity']:
                    raise ValueError("Capacity cannot be decreased")
                # update the train's capacity
                cursor.execute("UPDATE Trains SET capacity = %s WHERE train_id = %s;",
                               (train_capacity, train_key.to_int()))

            if train_status is not None:
                if train_status not in [TrainStatus.OPERATIONAL, TrainStatus.DELAYED, TrainStatus.BROKEN]:
                    raise ValueError("Invalid train status")
                cursor.execute("UPDATE Trains SET status = %s WHERE train_id = %s;",
                               (train_status.value, train_key.to_int()))  # value: 0 operational, 1 delayed, 2 broken

            if train_status == TrainStatus.BROKEN:
                # If the train is broken, cancel all reservations for the train
                cursor.execute("SELECT ticket_id FROM Tickets WHERE train_id = %s AND reserved_seat = TRUE", (train_key.to_int(),))
                reserved_tickets = cursor.fetchall()
                for (ticket_id,) in reserved_tickets:
                    cursor.execute("UPDATE Tickets SET reserved_seat = FALSE WHERE ticket_id = %s", (ticket_id,))

            self.rdbms_admin_connection.commit()

    def delete_train(self, train_key: TraitsKey) -> None:
        """
        Drop the train from the system. Note that all its schedules, reservations, etc. must be also dropped.
        """
        # Delete Train Schedules from Neo4j
        delete_schedules_cypher = """
               MATCH (t:Train {id: $train_id})-[r:SCHEDULE]->()
               DELETE r
               """
        with self.neo4j_driver.session() as session:
            session.run(delete_schedules_cypher, train_id=train_key.to_string())

        # Delete Train's Tickets from RDBMS
        with self.rdbms_admin_connection.cursor() as cursor:
            delete_tickets_sql = "DELETE FROM Tickets WHERE train_id = %s"
            cursor.execute(delete_tickets_sql, (train_key.to_int(),))
            self.rdbms_admin_connection.commit()

            # Delete Train from RDBMS
            delete_train_sql = "DELETE FROM Trains WHERE train_id = %s"
            cursor.execute(delete_train_sql, (train_key.to_int(),))
            self.rdbms_admin_connection.commit()

    def add_train_station(self, train_station_key: TraitsKey, train_station_details) -> None:
        """
        Add a train station
        Duplicated are not allowed, raise ValueError
        """

        with self.neo4j_driver.session() as session:
            # check if a station with the given key already exists
            result = session.run("MATCH (s:Station {station_id: $station_id}) RETURN s", station_id=train_station_key.to_int())
            if result.single() is not None:
                raise ValueError("Station already exists")

            # if the station does not exist, create a new station node
            session.run("CREATE (s:Station {station_id: $station_id, details: $details})", station_id=train_station_key.to_int(), details=train_station_details)

    def connect_train_stations(self, starting_train_station_key: TraitsKey, ending_train_station_key: TraitsKey,
                               travel_time_in_minutes: int) -> None:
        """
        Connect to train station so trains can travel on them
        Raise ValueError if any of the stations does not exist
        Raise ValueError for invalid travel_times
        """
        # requirements:
        if starting_train_station_key.to_string() == ending_train_station_key.to_string():
            raise ValueError("A station cannot be connected to itself")

        if not 1 <= travel_time_in_minutes <= 60:  # travel time must be between 1 and 60 minutes
            raise ValueError("Invalid travel time")

        # Calculate the travel price based on the travel time
        travel_price = travel_time_in_minutes / 2

        with self.neo4j_driver.session() as session:  # automatically closes the session
            # check if the starting and ending stations exist
            result_start = session.run("MATCH (s:Station {station_id: $station_id}) RETURN s",
                                        station_id=starting_train_station_key.to_int())
            result_end = session.run("MATCH (s:Station {station_id: $station_id}) RETURN s",
                                        station_id=ending_train_station_key.to_int())
            if result_start.single() is None or result_end.single() is None:
                raise ValueError("One or both stations do not exist")

            # check if a connection already exists between the two stations
            result = session.run("""
                    MATCH (a:Station {station_id: $start_id})-[:CONNECTION]->(b:Station {station_id: $end_id})
                    RETURN a, b
                """, start_id=starting_train_station_key.to_int(), end_id=ending_train_station_key.to_int())
            if result.single() is not None:
                raise ValueError("The same two stations cannot be directly connected more than once")

            # if both stations exist, create a relationship between them with the given travel time
            session.run("""
                MATCH (a:Station {station_id: $start_id}), (b:Station {station_id: $end_id})
                CREATE (a)-[:CONNECTION {travel_time: $travel_time,  price: $price}]->(b)
            """, start_id=starting_train_station_key.to_int(), end_id=ending_train_station_key.to_int(),
                        travel_time=travel_time_in_minutes, price=travel_price)

    def add_schedule(self, train_key: TraitsKey,
                     starting_hours_24_h: int, starting_minutes: int,
                     stops: List[Tuple[TraitsKey, int]],  # [station_key, waiting_time]
                     valid_from_day: int, valid_from_month: int, valid_from_year: int,
                     valid_until_day: int, valid_until_month: int, valid_until_year: int) -> None:
        """
        Create a schedule for a give train.
        The schedule must have at least two stops, cannot connect the same station directly but can create "rings"
        Stops must correspond to existing stations
        Consecutive stops must be connected stations.
        starting hours and minutes defines when this schedule is active
        Validity dates must ensure that valid_from is in the past w.r.t. valid_until
        In case of error, raise ValueError
        """

        # simplify the input parameters
        valid_from = datetime(valid_from_year, valid_from_month, valid_from_day)
        valid_until = datetime(valid_until_year, valid_until_month, valid_until_day)

        # validate the input parameters
        if train_key is None:
            raise ValueError("train_key cannot be None")
        elif any(stop[0] is None for stop in stops):
            raise ValueError("None of the TraitsKey objects in stops can be None")
        elif len(stops) < 2:
            raise ValueError("The schedule must have at least two stops")

        elif valid_from >= valid_until:
            raise ValueError("Validity dates must ensure that valid_from is in the past w.r.t. valid_until")

        # Check if the train exists
        with self.rdbms_admin_connection.cursor() as cursor:
            cursor.execute("SELECT * FROM Trains WHERE train_id = %s", (train_key.to_int(),))
            train = cursor.fetchone()
            if train is None:
                raise ValueError("Train does not exist")

        with self.neo4j_driver.session() as session:
            # check if the stops correspond to existing stations and if consecutive stops are connected
            for i in range(len(stops) - 1):  # check all stops except the last one (no connection needed)
                result_start = session.run("MATCH (s:Station {station_id: $station_id}) RETURN s",
                                            station_id=stops[i][0].to_int())
                result_end = session.run("MATCH (s:Station {station_id: $station_id}) RETURN s",
                                            station_id=stops[i + 1][0].to_int())
                if result_start.single() is None or result_end.single() is None:
                    raise ValueError("One or both stations do not exist")

                result_connection = session.run("""
                    MATCH (a:Station {station_id: $start_id})-[:CONNECTION]->(b:Station {station_id: $end_id})
                    RETURN a, b
                """, start_id=stops[i][0].to_int(), end_id=stops[i + 1][0].to_int())
                if result_connection.single() is None:
                    raise ValueError("Consecutive stops must be connected stations")

            # Convert TraitsKey objects to integers
            stops = [(stop[0].to_int(), stop[1]) for stop in stops]

            # create a new schedule for the train with the given parameters
            result = session.run("""
                CREATE (s:Schedule {train_id: $train_id,
                starting_hours_24_h: $starting_hours_24_h,
                starting_minutes: $starting_minutes,
                valid_from: $valid_from,
                valid_until: $valid_until})
                RETURN id(s)
            """, train_id=train_key.to_int(), starting_hours_24_h=starting_hours_24_h, starting_minutes=starting_minutes,
                                 valid_from=valid_from.isoformat(), valid_until=valid_until.isoformat())

            schedule_id = result.single()[0]  # get the ID of the newly created schedule

            # create a new Stop node for each stop and connect it to the Schedule node
            for i, stop in enumerate(stops):
                session.run("""
                    MATCH (s:Schedule) WHERE id(s) = $schedule_id
                    CREATE (stop:Stop {station_id: $station_id, waiting_time: $waiting_time, order: $order})
                    CREATE (s)-[:Has_Stops]->(stop)
                """, schedule_id=schedule_id, station_id=stop[0], waiting_time=stop[1], order=i)

