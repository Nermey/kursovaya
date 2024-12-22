from datetime import datetime, timedelta, time
import random
from concurrent.futures import ThreadPoolExecutor

buses_count = 8
route_duration = timedelta(minutes=60)
week = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
open_time = datetime.combine(datetime.today(), time(6))
close_time = datetime.combine(datetime.today(), time(3)) + timedelta(days=1)

peak_hours = [(datetime.combine(datetime.today(), time(hour=7)), datetime.combine(datetime.today(), time(hour=9))),
              (datetime.combine(datetime.today(), time(hour=17)), datetime.combine(datetime.today(), time(hour=19)))]

not_peak_hours_workload = 0.5
peak_hours_workload = 0.7

generations = 20
mutation_percent = 0.3
population_size = 5


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
            while current_day < len(week):
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


def set_drivers_on_routes(schedule, individual) -> None:
    drivers = []
    drivers_types = {0: "A", 1: "B"}
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

                if individual:
                    new_driver = Driver(driver_id=len(drivers) + 1,
                                        driver_type=drivers_types[individual.pop(0)],
                                        shift_start=route)
                    new_driver.make_driver_schedule(schedule, bus_id)
                    drivers.append(new_driver)
                    work_days = [d for d in week if d not in new_driver.weekends]
                    for d in work_days:
                        buses[d][bus_id] = (
                            new_driver.shift_start.start_time, new_driver.end_day_time + timedelta(minutes=15))


def generate_population():
    length = random.randint(buses_count * 2, buses_count * 6)
    return [[random.choice([0, 1]) for _ in range(length)] for _ in range(population_size)]


all_routes = sum(1 for day_routes in generate_empty_schedule().values() for route in day_routes if not route.has_driver)


def fitness(individual):
    assigned_routes = set()
    driver_index = 0

    for day, routes in generate_empty_schedule().items():
        for route in routes:
            if driver_index >= len(individual):
                break

            if not route.has_driver and individual[driver_index] == 1:
                route.has_driver = True
                assigned_routes.add(route)
                driver_index += 1

    return len(assigned_routes) / all_routes


def tournament_selection(population, fitnesses):
    i1, i2, i3 = random.sample(range(len(population)), 3)
    if fitnesses[i1] > fitnesses[i2] and fitnesses[i1] > fitnesses[i3]:
        return population[i1]
    elif fitnesses[i2] > fitnesses[i1] and fitnesses[i2] > fitnesses[i3]:
        return population[i2]
    else:
        return population[i3]


def crossover(parent1, parent2):
    point = random.randint(0, min(len(parent1), len(parent2)) - 1)
    child1 = parent1[:point] + parent2[point:]
    child2 = parent2[:point] + parent1[point:]

    return child1, child2


def mutate(individual):
    if random.random() < mutation_percent:
        gen_idx = random.randint(0, len(individual) - 1)
        individual[gen_idx] = 1 - individual[gen_idx]
    return individual


def genetic_algorithm():
    population = generate_population()

    generation = 0
    best_individual = []

    with ThreadPoolExecutor() as executor:
        while generation < generations:
            fitnesses = list(executor.map(lambda ind: fitness(ind), population))
            best_fitness = max(fitnesses)
            best_individual = population[fitnesses.index(best_fitness)]

            new_population = []
            num_offspring = 0

            num_parents = population_size // 2

            parent_indices = set()
            while len(parent_indices) < num_parents * 2:
                parent = tournament_selection(population, fitnesses)
                idx = population.index(parent)
                parent_indices.add(idx)

            parent_indices = list(parent_indices)
            random.shuffle(parent_indices)

            for i in range(0, len(parent_indices), 2):
                parent1 = population[parent_indices[i]]
                parent2 = population[parent_indices[i + 1]]
                child1, child2 = crossover(parent1, parent2)
                new_population.extend([child1, child2])
                num_offspring += 2

            individuals_not_selected = [population[i] for i in range(population_size) if i not in parent_indices]
            new_population.extend(individuals_not_selected)

            for individual in new_population:
                mutate(individual)

            population = new_population[:population_size]

            generation += 1

    return best_individual


schedule = generate_empty_schedule()
best_individual = genetic_algorithm()
print("количество водителей", len(best_individual))
set_drivers_on_routes(schedule, best_individual)
for day, routes in schedule.items():
    print(f"{day}:")
    for route in routes:
        driver_info = f"Driver {route.driver.driver_id}" if route.driver else "No driver"
        print(
            f"  {route.start_time.strftime('%H:%M')} - {route.end_time.strftime('%H:%M')} | {driver_info} bus: {route.bus_id}")
