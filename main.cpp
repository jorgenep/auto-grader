#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <string>

int main() {
    constexpr std::size_t kCapacity = 100;
    double weights[kCapacity];
    std::size_t count = 0;

    std::string filename = "dino_weights.txt";
    std::string stdin_line;
    if (std::getline(std::cin, stdin_line)) {
        if (!stdin_line.empty()) {
            filename = stdin_line;
        }
    }

    std::ifstream input(filename);
    if (!input) {
        std::cerr << "Failed to open file: " << filename << '\n';
        return 1;
    }

    while (count < kCapacity && (input >> weights[count])) {
        ++count;
    }

    if (count == 0) {
        std::cout << "No weights were read from the file." << std::endl;
        return 0;
    }

    double total = 0.0;
    double minimum = std::numeric_limits<double>::max();
    double maximum = std::numeric_limits<double>::lowest();

    for (std::size_t i = 0; i < count; ++i) {
        total += weights[i];
        if (weights[i] < minimum) {
            minimum = weights[i];
        }
        if (weights[i] > maximum) {
            maximum = weights[i];
        }
    }

    double average = total / static_cast<double>(count);

    std::cout << std::fixed << std::setprecision(2);
    std::cout << "Total weight: " << total << '\n';
    std::cout << "Average weight: " << average << '\n';
    std::cout << "Smallest (min) weight: " << minimum << '\n';
    std::cout << "Largest (max) weight: " << maximum << std::endl;

    return 0;
}
