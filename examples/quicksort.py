def quicksort_pythonic(list_in, order="asc"):
    left_list = []
    equal_list = []
    right_list = []

    if len(list_in) > 1:
        pivot = list_in[0]
        for x in list_in:
            if x == pivot:
                equal_list.append(x)
            if order == "asc":
                if x < pivot:
                    left_list.append(x)
                if x > pivot:
                    right_list.append(x)
            if order == "desc":
                if x > pivot:
                    left_list.append(x)
                if x < pivot:
                    right_list.append(x)
        return quicksort_pythonic(left_list, order) + equal_list + quicksort_pythonic(right_list, order)
    else:
        # list size is too small for sorting, just return it
        return list_in

l = [3,5,7,3,2,5,1,6,0,1,2]
print(quicksort_pythonic(l, "asc"))
