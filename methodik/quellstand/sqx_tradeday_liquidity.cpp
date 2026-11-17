// Match frozen SQX executions to TBBO and book only displayed or replenished size.
#include <algorithm>
#include <array>
#include <cstdio>
#include <fstream>
#include <iostream>
#include <limits>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>
#include <zlib.h>

using I = long long;
constexpr I tick_value = 500;
constexpr I fee = 288;

struct Quote { I time; int bid, ask, bid_size, ask_size; };
struct Trigger { I time; int side, price; bool entry; };

struct OrderStream {
    std::vector<Trigger> orders;
    size_t next = 0;

    const Trigger* at(const Quote& q) {
        if (next == orders.size() || q.time < orders[next].time) return nullptr;
        const auto& s = orders[next];
        if (q.time > s.time) throw std::runtime_error("SQX order does not match the observed quote");
        return (s.side > 0 ? q.ask : q.bid) == s.price ? &orders[next++] : nullptr;
    }
};

struct Level {
    int price = 0, shown = 0, available = 0;

    void update(int px, int size, bool pending) {
        if (px != price || !pending) available = size;
        else available = std::clamp(available + size - shown, 0, size);
        price = px;
        shown = size;
    }
};

struct Slot {
    int side = 0, left = 0, size = 0, trades = 0, legs = 0, unfilled = 0, skipped = 0;
    bool exiting = false;
    I cash = 0, target_ns = 0, max_delay = 0, price_cost = 0;
    int target_price = 0, delayed = 0;
    std::array<I, 2> low{};
    std::array<int, 4> entry_prices{};

    bool active() const { return size || left; }

    void request(const Trigger& t, int quantity) {
        if (t.entry) {
            if (size || exiting) {
                ++skipped;
                return;
            }
            side = t.side;
            left = quantity;
        } else {
            unfilled += left;
            left = size;
            exiting = size > 0;
        }
        target_ns = t.time;
        target_price = t.price;
    }

    void mark(const Quote& q) {
        I value = cash;
        const int price = side > 0 ? q.bid : q.ask;
        for (int i = 0; i < size; ++i) value += I(side) * (price - entry_prices[i]) * tick_value;
        low[0] = std::min(low[0], value);
        low[1] = std::min(low[1], value - tick_value * legs);
    }

    void fill(Level& level, I now) {
        const int quantity = std::min(left, level.available);
        if (!quantity) return;
        level.available -= quantity;
        left -= quantity;
        legs += quantity;
        cash -= fee * quantity;
        price_cost += I(quantity) * (exiting ? -side : side) * (level.price - target_price);
        if (now > target_ns) {
            delayed += quantity;
            max_delay = std::max(max_delay, now - target_ns);
        }
        if (exiting) {
            for (int i = 0; i < quantity; ++i)
                cash += I(side) * (level.price - entry_prices[i]) * tick_value;
            size -= quantity;
            for (int i = 0; i < size; ++i) entry_prices[i] = entry_prices[quantity + i];
            if (!size) {
                ++trades;
                exiting = false;
            }
        } else {
            for (int i = 0; i < quantity; ++i) entry_prices[size++] = level.price;
        }
    }
};

struct SharedBook {
    int quantity, width, phase_code;
    std::array<int, 5> phases{};
    std::array<Slot, 5> slots{};
    Level bid{}, ask{};
    int open_slots = 0;

    SharedBook(int quantity, int width, int phase_code)
        : quantity(quantity), width(width), phase_code(phase_code) {
        for (int i = width - 1, code = phase_code; i >= 0; --i, code /= 3)
            phases[i] = code % 3;
    }

    void tick(const Quote& q, const std::array<const Trigger*, 3>& triggers) {
        if (!open_slots && !triggers[1] && !triggers[2]) return;
        bool pending_bid = false, pending_ask = false;
        for (int i = 0; i < width; ++i) {
            const auto& slot = slots[i];
            const int direction = slot.exiting ? -slot.side : slot.side;
            pending_bid |= slot.left && direction < 0;
            pending_ask |= slot.left && direction > 0;
        }
        bid.update(q.bid, q.bid_size, pending_bid);
        ask.update(q.ask, q.ask_size, pending_ask);
        for (int i = 0; i < width; ++i)
            if (const auto* trigger = triggers[phases[i]]) slots[i].request(*trigger, quantity);
        for (bool exiting : {true, false}) {
            for (int i = 0; i < width; ++i) {
                auto& slot = slots[i];
                if (slot.left && slot.exiting == exiting)
                    slot.fill((exiting ? -slot.side : slot.side) > 0 ? ask : bid, q.time);
            }
        }
        open_slots = 0;
        for (int i = 0; i < width; ++i) {
            slots[i].mark(q);
            open_slots += slots[i].active();
        }
    }

    void finish(int day, bool extended) {
        for (int i = 0; i < width; ++i) {
            const auto& s = slots[i];
            if (s.active()) throw std::runtime_error("Unfilled exit or open position at the session boundary");
            std::cout << day << ',' << quantity << ',';
            if (extended) std::cout << width << ',' << phase_code;
            else std::cout << phases[0] << ',' << phases[1];
            std::cout << ',' << i << ',' << s.cash << ',' << s.low[0] << ',' << s.cash - tick_value * s.legs
                      << ',' << s.low[1] << ',' << s.trades << ',' << s.legs << ',' << s.delayed
                      << ',' << s.max_delay << ',' << s.price_cost << ',' << s.unfilled << ',' << s.skipped << '\n';
        }
        slots = {};
        open_slots = 0;
        bid = ask = {};
    }
};

int main(int argc, char** argv) try {
    if (argc != 5 && argc != 6)
        throw std::runtime_error("Expected tape, carrier CSV, schedule, callback count and optional portfolio flag");
    const bool extended = argc == 6 && std::string(argv[5]) == "--portfolio";
    if (argc == 6 && !extended) throw std::runtime_error("Unexpected portfolio flag");
    gzFile tape = gzopen(argv[1], "rb");
    std::ifstream book(argv[2]), schedule(argv[3]);
    if (!tape || !book || !schedule) throw std::runtime_error("Missing execution input");
    gzbuffer(tape, 1 << 20);
    std::array<OrderStream, 3> streams;
    int phase, action;
    Trigger order;
    while (schedule >> phase >> order.time >> order.side >> order.price >> action) {
        if (phase < 1 || phase > 2 || (order.side != 1 && order.side != -1))
            throw std::runtime_error("Invalid SQX order");
        order.entry = action == 1;
        streams[phase].orders.push_back(order);
    }
    std::vector<SharedBook> scenarios;
    if (extended) {
        for (int q = 1; q <= 4; ++q) {
            std::vector<int> codes{0};
            for (int width = 1; width <= 5; ++width) {
                std::vector<int> next;
                for (int prefix : codes) {
                    for (int phase : {1, 2}) {
                        next.push_back(prefix * 3 + phase);
                        scenarios.emplace_back(q, width, next.back());
                    }
                }
                codes = std::move(next);
            }
        }
    } else {
        for (int q : {1, 2})
            for (int first : {1, 2})
                for (int second : {0, 1, 2}) scenarios.emplace_back(q, 2, first * 3 + second);
    }

    std::string carrier;
    if (!std::getline(book, carrier) || carrier.find("DateTime,Bid,Ask,BidVolume,AskVolume") != 0)
        throw std::runtime_error("Unexpected quote carrier");
    char line[224];
    I seen = 0, previous = 0;
    int active_day = -1;
    while (gzgets(tape, line, sizeof(line))) {
        ++seen;
        if (!std::getline(book, carrier)) throw std::runtime_error("Short quote carrier");
        I ms, ns;
        int day, bid, ask, kind;
        if (std::sscanf(line, "%lld,%lld,%d,%d,%d,%d", &ms, &ns, &day, &bid, &ask, &kind) != 6
                || ns < previous || (active_day >= 0 && day < active_day))
            throw std::runtime_error("Invalid quote tape order");
        previous = ns;
        if (day != active_day) {
            if (active_day >= 0) for (auto& scenario : scenarios) scenario.finish(active_day, extended);
            active_day = day;
        }
        if (kind != 1) continue;
        Quote q{ns, bid, ask, 0, 0};
        const std::array<const Trigger*, 3> triggers{nullptr, streams[1].at(q), streams[2].at(q)};
        const auto comma = carrier.find(',');
        double carried_bid, carried_ask;
        if (comma == std::string::npos ||
            std::sscanf(carrier.c_str() + comma + 1, "%lf,%lf,%d,%d", &carried_bid, &carried_ask, &q.bid_size, &q.ask_size) != 4
                || carried_bid * 4 != bid || carried_ask * 4 != ask || q.bid_size < 1 || q.ask_size < 1)
            throw std::runtime_error("Quote carrier differs from TBBO");
        for (auto& scenario : scenarios) scenario.tick(q, triggers);
    }
    if (std::getline(book, carrier) || gzclose(tape) != Z_OK || seen != std::stoll(argv[4]))
        throw std::runtime_error("Incomplete annual quote segment");
    for (const auto& stream : streams)
        if (stream.next != stream.orders.size()) throw std::runtime_error("Unmatched SQX order");
    for (auto& scenario : scenarios) scenario.finish(active_day, extended);
    std::cerr << seen << " matched quote callbacks\n";
    return 0;
} catch (const std::exception& e) {
    std::cerr << e.what() << '\n';
    return 1;
}
