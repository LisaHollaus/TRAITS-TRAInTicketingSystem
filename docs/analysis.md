## Requirements:
### A passenger must
•   own a name, id and email address.

•	be able to purchase a ticket.

•	be able to reserve a place in a train with a given number of railway cars that have numbered seats.

•	be able to take a train journey.
### A train must 
•	be able to travel between two locations.

•	possess cars with seats.

•	own a current location.
### A ticket must be
•	valid for a period of time.

•	validated when used.

•	display departure and destination station.
## Objects and attributes:
    Passenger (name, email_address, id)

    Ticket (number, valid_from, valid_until, departure_station, destination_station, valid=boolean)

    Train (id, total_capacity, location)

    Car (id, capacity, class)

    Seat (number) <- depends on Car (weak entity)

    Station (name, id, address)

## Relationships:
    purchases (Passenger, Ticket)

A Passenger can purchase multiple Tickets, but a specific Ticket can only be purchased by one Passenger.

    validated (Ticket, Train)

One Train can have multiple Tickets associated with it, but one Ticket can only be validated for one Train.

    reserves (Passenger, Seat)

A Passenger can reserve multiple Seats, but a specific Seat can only be reserved by one Passenger.

    takes_journey (Train, Station) - attributes: duration, departure_station, destination_station

Each Train can travel to multiple Stations and multiple trains can travel to the same station.

    possesses (Train, Car)

Each Train must have at least one up to multiple Cars, but a Car can only be assigned to one specific Train.

    possesses (Car, Seat)

Each Car must have at least one up to multiple Seats, but a Seat can only be assigned to one specific Car.
