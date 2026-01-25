"use client";

import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { cn } from "@/lib/utils";

interface MenuProps {
  children: React.ReactNode;
  trigger: React.ReactNode;
}

export function Menu({ children, trigger }: MenuProps) {
  return (
    <DropdownMenu.Root>
      <DropdownMenu.Trigger asChild>{trigger}</DropdownMenu.Trigger>
      <DropdownMenu.Portal>
        <DropdownMenu.Content
          className={cn(
            "min-w-[180px] bg-white dark:bg-gray-900 rounded-lg shadow-lg",
            "border border-gray-200 dark:border-gray-700 p-1 z-50",
            "data-[state=open]:animate-in data-[state=closed]:animate-out",
            "data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0",
            "data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95"
          )}
          sideOffset={5}
          align="end"
        >
          {children}
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  );
}

interface MenuItemProps {
  children: React.ReactNode;
  onClick?: () => void;
  destructive?: boolean;
  disabled?: boolean;
}

export function MenuItem({
  children,
  onClick,
  destructive = false,
  disabled = false,
}: MenuItemProps) {
  return (
    <DropdownMenu.Item
      className={cn(
        "flex items-center px-3 py-2 text-sm rounded-md cursor-pointer outline-none",
        "transition-colors",
        destructive
          ? "text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 focus:bg-red-50 dark:focus:bg-red-900/20"
          : "text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 focus:bg-gray-100 dark:focus:bg-gray-800",
        disabled && "opacity-50 cursor-not-allowed"
      )}
      onClick={onClick}
      disabled={disabled}
    >
      {children}
    </DropdownMenu.Item>
  );
}

export function MenuSeparator() {
  return (
    <DropdownMenu.Separator className="h-px my-1 bg-gray-200 dark:bg-gray-700" />
  );
}
