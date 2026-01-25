import { useQuery } from "@tanstack/react-query";
import { fetchSnapshots, fetchCategories, fetchGroups } from "@/lib/api";
import { NetWorthSnapshot, NetWorthCategory, NetWorthGroup } from "@/types";

export function useNetWorthSnapshots() {
  return useQuery<NetWorthSnapshot[]>({
    queryKey: ["networth-snapshots"],
    queryFn: fetchSnapshots,
  });
}

export function useNetWorthCategories() {
  return useQuery<NetWorthCategory[]>({
    queryKey: ["networth-categories"],
    queryFn: fetchCategories,
  });
}

export function useNetWorthGroups() {
  return useQuery<NetWorthGroup[]>({
    queryKey: ["networth-groups"],
    queryFn: fetchGroups,
  });
}
