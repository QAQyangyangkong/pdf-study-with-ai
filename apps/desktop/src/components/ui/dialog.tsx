// shadcn/ui Dialog, adapted from the MIT-licensed new-york registry.
import * as React from 'react';
import * as DialogPrimitive from '@radix-ui/react-dialog';
import { X } from 'lucide-react';
import { cn } from '../../lib/utils';

const Dialog = DialogPrimitive.Root;
const DialogTitle = DialogPrimitive.Title;
const DialogDescription = DialogPrimitive.Description;

const DialogContent = React.forwardRef<
  React.ComponentRef<typeof DialogPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Content>
>(({ className, children, ...props }, ref) => (
  <DialogPrimitive.Portal>
    <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-[#26382c]/30 backdrop-blur-sm" />
    <DialogPrimitive.Content
      ref={ref}
      className={cn('fixed left-1/2 top-1/2 z-50 max-h-[90vh] w-[min(760px,calc(100%-50px))] -translate-x-1/2 -translate-y-1/2 overflow-auto rounded-xl border border-border bg-background p-7 shadow-xl', className)}
      {...props}
    >
      {children}
      <DialogPrimitive.Close className="absolute right-5 top-5 rounded-md p-1.5 text-muted-foreground hover:bg-accent focus-visible:outline-2 focus-visible:outline-ring" aria-label="关闭弹窗">
        <X size={20} />
      </DialogPrimitive.Close>
    </DialogPrimitive.Content>
  </DialogPrimitive.Portal>
));
DialogContent.displayName = 'DialogContent';

export { Dialog, DialogContent, DialogTitle, DialogDescription };
