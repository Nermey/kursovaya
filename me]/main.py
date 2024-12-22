from datetime import datetime, timedelta, time

buses_count = int(input("Введите количество автобусов:"))
route_duration = timedelta(minutes=60)
week = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
open_time = datetime.combine(datetime.today(), time(6))
close_time = datetime.combine(datetime.today(), time(3)) + timedelta(days=1)

peak_hours = [(datetime.combine(datetime.today(), time(hour=7)), datetime.combine(datetime.today(), time(hour=9))),
              (datetime.combine(datetime.today(), time(hour=17)), datetime.combine(datetime.today(), time(hour=19)))]

not_peak_hours_workload = 0.5
peak_hours_workload = 0.7


class Driver:
    def __init__(self, driver_id: int, driver_type: str, shift_start) -> None:
        self.driver_id = driver_id
        self.driver_type = driver_type
        self.shift_start = shift_start
        self.weekends = []
        self.breaks = []
        self.days_last_routes = {}
        for day in week:
            self.days_last_routes[day] = self.shift_start.start_time

        if self.driver_type == "A":
            self.end_day_time = self.shift_start.start_time + timedelta(hours=9)
            self.weekends = week[-2:]
            self.breaks.append((self.shift_start.start_time + timedelta(hours=4),
                                self.shift_start.start_time + timedelta(hours=5)))

        else:
            self.end_day_time = self.shift_start.start_time + timedelta(hours=12)

            work_days = []
            current_day = week.index(self.shift_start.day)
            while current_day <= len(week):
                work_days.append(week[current_day])
                current_day += 3
            self.weekends.extend([i for i in week if i not in work_days])

            current_time = self.shift_start.start_time + timedelta(hours=2, minutes=15)
            while current_time < self.shift_start.start_time + timedelta(hours=12):
                self.breaks.append((current_time - timedelta(minutes=15), current_time))
                current_time += timedelta(hours=2, minutes=15)

        self.breaks = [b for b in self.breaks
                       if b[0] < close_time and
                       b[1] < close_time]

    def route_in_break(self, route) -> bool:
        for b in self.breaks:
            if not (route.end_time <= b[0] or route.start_time >= b[1]):
                return False
        return True

    def make_driver_schedule(self, schedule: dict, bus_id: int) -> None:
        for day, routes in schedule.items():
            if day in self.weekends:
                continue

            last_end_time = self.days_last_routes[day]

            for route in routes:
                if (
                        not route.has_driver and
                        last_end_time <= route.start_time < self.end_day_time and
                        self.route_in_break(route)
                ):
                    current_route = route
                    while current_route:
                        if current_route.day not in self.weekends and self.route_in_break(route):
                            current_route.set_driver(driver=self, bus_id=bus_id)
                            last_end_time = current_route.end_time
                            self.days_last_routes[current_route.day] = current_route.end_time
                        current_route = current_route.next_day_route


class Route:
    def __init__(self, start_time, end_time, day) -> None:
        self.start_time = start_time
        self.end_time = end_time
        self.day = day
        self.has_driver = False
        self.next_day_route = None
        self.driver = None
        self.bus_id = None

    def set_next_day_route(self, route) -> None:
        self.next_day_route = route

    def set_driver(self, driver: Driver, bus_id) -> None:
        self.has_driver = True
        self.driver = driver
        self.bus_id = bus_id


def generate_empty_schedule() -> dict:
    peek_bus_cnt = int(peak_hours_workload * buses_count)
    not_peek_bus_cnt = int(not_peak_hours_workload * buses_count)

    interval_in_not_peak_hours = route_duration // not_peek_bus_cnt
    interval_in_peak_hours = route_duration // peek_bus_cnt
    bus_schedule = {day: [] for day in week}
    for day in week:
        current_time = open_time
        day_schedule = []
        active_routes = []
        while current_time < close_time:
            current_bus_count = not_peek_bus_cnt
            interval = interval_in_not_peak_hours

            active_routes = [route for route in active_routes if route.end_time > current_time]

            if ((peak_hours[0][0] <= current_time < peak_hours[0][1]) or (
                    peak_hours[1][0] <= current_time < peak_hours[1][1])) \
                    and day not in week[-2:]:
                current_bus_count = peek_bus_cnt
                interval = interval_in_peak_hours

            if len(active_routes) < current_bus_count:
                route = Route(start_time=current_time, end_time=current_time + route_duration, day=day)
                if route.end_time <= close_time:
                    active_routes.append(route)
                    day_schedule.append(route)

            current_time += interval

        bus_schedule[day] = day_schedule

    for i, day in enumerate(week[:-1]):
        next_day = week[i + 1]
        for route in bus_schedule[day]:
            next_day_routes = bus_schedule[next_day]
            for next_route in next_day_routes:
                if route.start_time == next_route.start_time and route.end_time == next_route.end_time:
                    route.set_next_day_route(next_route)
                    break

    return bus_schedule


def set_drivers_on_routes(schedule):
    drivers = []

    buses = {}
    for day in week:
        day_buses = {}
        for i in range(buses_count):
            day_buses[i] = (open_time - timedelta(minutes=15), open_time - timedelta(minutes=15))
        buses[day] = day_buses

    for day, routes in schedule.items():
        for route in routes:
            if route.has_driver:
                continue

            bus_id = None
            for bid, (start, end) in buses[day].items():
                if end <= route.start_time or start >= route.end_time:
                    bus_id = bid
                    break
            else:
                route.has_driver = True
                continue

            if bus_id is not None:
                if day in week[:5]:
                    new_driver_type = "A"
                else:
                    new_driver_type = "B"

                new_driver = Driver(driver_id=len(drivers) + 1,
                                    driver_type=new_driver_type,
                                    shift_start=route)
                new_driver.make_driver_schedule(schedule, bus_id)
                drivers.append(new_driver)
                work_days = [d for d in week if d not in new_driver.weekends]
                for d in work_days:
                    buses[d][bus_id] = (new_driver.shift_start.start_time, new_driver.end_day_time + timedelta(minutes=15))

    print(f"Количество водителей: {len(drivers)}")


schedule = generate_empty_schedule()
set_drivers_on_routes(schedule)
for day, routes in schedule.items():
    print(f"{day}:")
    for route in routes:
        driver_info = f"Driver {route.driver.driver_id}" if route.driver else "No driver"
        print(
            f"  {route.start_time.strftime('%H:%M')} - {route.end_time.strftime('%H:%M')} | {driver_info} bus: {route.bus_id}")
