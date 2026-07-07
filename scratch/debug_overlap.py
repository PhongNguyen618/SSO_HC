h1, m1 = map(int, "05:13".split(":"))
h2, m2 = map(int, "05:13".split(":"))
start1 = h1 * 60 + m1
start2 = h2 * 60 + m2

dur1 = 56.23
dur2 = 57.4

end1 = start1 + dur1
end2 = start2 + dur2

overlap_mins = max(0.0, min(end1, end2) - max(start1, start2))
min_dur = min(dur1, dur2)

print(f"start1: {start1}, end1: {end1}")
print(f"start2: {start2}, end2: {end2}")
print(f"overlap_mins: {overlap_mins}")
print(f"min_dur: {min_dur}")

if min_dur > 0:
    overlap_ratio = overlap_mins / min_dur
    print(f"overlap_ratio: {overlap_ratio}")
    print(f"abs_diff_start: {abs(start1 - start2)}")
    if overlap_ratio > 0.5 and abs(start1 - start2) <= 15:
        print("OVERLAP DETECTED = TRUE")
