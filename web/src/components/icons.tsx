import type { ReactNode, SVGProps } from "react";

type IconProps = SVGProps<SVGSVGElement> & { size?: number };

function Icon({ size = 16, children, ...rest }: IconProps & { children: ReactNode }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
      {...rest}
    >
      {children}
    </svg>
  );
}

export const PlusIcon = (p: IconProps) => <Icon {...p}><path d="M12 5v14M5 12h14" /></Icon>;
export const TrashIcon = (p: IconProps) => (
  <Icon {...p}><path d="M4 7h16M10 11v6M14 11v6M6 7l1 12a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2l1-12M9 7V4h6v3" /></Icon>
);
export const ArrowUpIcon = (p: IconProps) => <Icon {...p}><path d="M12 19V5M6 11l6-6 6 6" /></Icon>;
export const CopyIcon = (p: IconProps) => (
  <Icon {...p}><rect x="9" y="9" width="11" height="11" rx="2" /><path d="M5 15V6a2 2 0 0 1 2-2h9" /></Icon>
);
export const CheckIcon = (p: IconProps) => <Icon {...p}><path d="M5 12.5l4.5 4.5L19 7" /></Icon>;
export const MenuIcon = (p: IconProps) => <Icon {...p}><path d="M4 7h16M4 12h16M4 17h16" /></Icon>;
export const CloseIcon = (p: IconProps) => <Icon {...p}><path d="M6 6l12 12M18 6L6 18" /></Icon>;
export const BackIcon = (p: IconProps) => <Icon {...p}><path d="M15 6l-6 6 6 6" /></Icon>;
export const ChevronDownIcon = (p: IconProps) => <Icon {...p}><path d="M6 9l6 6 6-6" /></Icon>;
export const PenIcon = (p: IconProps) => <Icon {...p}><path d="M4 20h4L19 9l-4-4L4 16v4zM13.5 6.5l4 4" /></Icon>;
export const PageIcon = (p: IconProps) => (
  <Icon {...p}><path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" /><path d="M14 3v5h5M9 13h6M9 17h6" /></Icon>
);
export const ChatIcon = (p: IconProps) => <Icon {...p}><path d="M5 18l-1 3 4-1.5A8.5 8.5 0 1 0 5 18z" /></Icon>;
export const LaptopIcon = (p: IconProps) => <Icon {...p}><rect x="4" y="5" width="16" height="11" rx="1.5" /><path d="M2 19h20" /></Icon>;
export const CloudIcon = (p: IconProps) => <Icon {...p}><path d="M7 18h10a4 4 0 0 0 .5-7.97A6 6 0 0 0 6 9.5 4.25 4.25 0 0 0 7 18z" /></Icon>;
export const LockIcon = (p: IconProps) => <Icon {...p}><rect x="5" y="11" width="14" height="9" rx="2" /><path d="M8 11V8a4 4 0 0 1 8 0v3" /></Icon>;
export const AlertIcon = (p: IconProps) => <Icon {...p}><path d="M12 4l9 16H3zM12 10v4M12 17.5v.01" /></Icon>;
export const InfoIcon = (p: IconProps) => <Icon {...p}><circle cx="12" cy="12" r="9" /><path d="M12 11v5M12 8v.01" /></Icon>;
export const PlayIcon = (p: IconProps) => <Icon {...p}><path d="M8 5.5v13l11-6.5z" /></Icon>;
