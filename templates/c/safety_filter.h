#ifndef SKYFORGE_SAFETY_FILTER_H
#define SKYFORGE_SAFETY_FILTER_H

#include <stdint.h>
#include <stdbool.h>

/* [REQ-C-001] [MISRA-Rule-8.13] Public filter state. */
typedef struct
{
    double last_output;
    bool initialized;
    bool fault_detected;
} SkyforgeSafetyFilter;

void skyforge_safety_filter_init(SkyforgeSafetyFilter * const filter);
double skyforge_safety_filter_step(SkyforgeSafetyFilter * const filter,
                                   const double raw_input);
bool skyforge_safety_filter_faulted(const SkyforgeSafetyFilter * const filter);

#endif /* SKYFORGE_SAFETY_FILTER_H */
