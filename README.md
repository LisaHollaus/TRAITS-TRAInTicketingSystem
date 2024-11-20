

## Traits
### Database Structure
To start of our assignment we discussed the requirements and the data we have and need to store.
From there we created/obtained the database schema for both MariaDB and Neo4j. 
We used the following structure:
#### MariaDB:
We chose to created 4 tables (Users, Trains, Tickets, PurchaseHistory) in MariaDB, because it allows us to create a structured schema with relations between the tables.
Since they are all related to each other, in a structured way we thought it would be best to use a relational database. 
As it also allows us to easily query the data and join the tables when needed.

Users table: 
- email (unique, primary key, Check for email format) 
- user_details 

We used email as the primary key and therefore didn't implement a user_id/ optionally we could have added it with AUTO_INCREMENT.
We also didn't add a password, as it wasn't required for the assignment, but we would have added it in a real-world scenario.
As we did not know what the user_details should contain, we left it like this.

Trains table: 
- train_id (auto increment, primary key)
- capacity (available seats)
- status (with check: 0 operational, 1 delayed, 2 broken)

Tickets table: 
- ticket_id (auto increment, primary key)
- user_email (foreign key)
- train_id (foreign key)
- purchase_date (Datetime)
- reserved_seats (Boolean, as we assumed that only one seat can be reserved per ticket, but multiple tickets can be bought at once)
- price (float)
- start_station 
- end_station

With foreign keys to Users and Trains and no NULL values allowed.
We also did not add any other attributes to be unique, because a user can book multiple tickets for the same train.

PurchaseHistory table: 
- user_email (foreign key)
- ticket_id (foreign key)
- purchase_date (Datetime)

With foreign keys to Users and Tickets and no NULL values allowed.
Primary key is a composite key of user_email and ticket_id.

#### Neo4j:  
When it came to the Neo4j database, we chose to create 3 nodes (Stations, Stop, Schedules) and 2 relationships/Edges (Connections, Has_Stops).
As the data is related to each other and dependent on a position/location with a given distance/time between them, we thought it would be best to use a graph database for them.

Schedule nodes: 
- train_id 
- starting_hours_24_h
- starting_minutes
- valid_from
- valid_until

Stops nodes:
- station_id
- waiting_time (in minutes)
- order 

Stations nodes:
- station_id
- details

Connections edges: Each edge represents a connection between two stations.
- travel_time (in minutes)
- price

Has_Stops edges: Each edge represents a train schedule having a stop. The edges are created between a Schedule node and a Stop node.


### Implementation
1. First of all we created a virtual environment, installed the required packages and connected to the databases using docker.
2. We implemented the database schema in MariaDB (generate_sql_initialization_code) and Neo4j (in methods, since the graph database seems to not need a basic structure and can get created/implemented right away).
3. Next, we started implementing the given methods, starting with the MariaDB methods and more simple queries (like add_user, get_all_users,...).
4. We then moved on to the more complex queries (like buy_ticket, search_connesctions,...) including the Neo4j methods.
- Throughout the implementation, we constantly tested the methods with the given test cases and some additional test cases we created ourselves.
- We also tested the methods with different data and edge cases to make sure the methods are working as expected.
- As well as making sure to handle exceptions and errors properly and return the correct error messages.
- We found the use of fixtures very helpful to test the methods and make sure they are working as expected.


### Additional Notes
- We added some requirement to the requirements.txt file, when implementing the GitHub action, but we ended up with having some issues with the path to the public module. Which we saddly weren't able to fix in time.
- For the get_train_current_status method, we had to use the admin_connection. We are aware that this should be accessible by anybody and would change this in a real-world scenario. But for the sake of passing the public tests, we had to use the admin_connection.
This is because, when we used the user_connection, we were not able to pass the test_update_train_details function, as it calls the add_train method, (which requires the admin_connection), shortly before calling get_train_current_status.
- As neo4j is/was still very new to us, we had some issues with the queries and the data representation in the beginning ,but if we would have had more time, we would have focused on improving the data representation in neo4j and the database schema overall, so that there is only a minimum amount of python code needed.
- We are also aware that we propably weren't able to fulfill all requirements, but we tried our best to implement as much as possible and make sure the code is working as expected.
- With more time, we would have also added more functions to improve the code and make it more user-friendly and efficient, with a focus on handling the validation of the data in the databases. 

After all we learned a lot along the way and hope that we can use this knowledge in the future to improve our coding skills and make better decisions when it comes to databases and data representation.