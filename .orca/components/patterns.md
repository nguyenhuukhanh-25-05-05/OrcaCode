# Component Patterns — Selection & Composition Guide

> **Module:** Implementation  
> **Read Time:** 4 minutes  
> **When:** Phase 2 — Component Structure

---

## 1. COMPONENT DECISION TREE

```
Need a button?
  → <Button variant="primary|secondary|outline|ghost" />

Need form input?
  → Text: <FieldGroup><Field><FieldLabel/><Input/></Field></FieldGroup>
  → Select: <Select><SelectTrigger/><SelectContent/></Select>
  → Toggle 2-7: <ToggleGroup><ToggleGroupItem/></ToggleGroup>

Need modal/overlay?
  → Modal: <Dialog><DialogTrigger/><DialogContent/></Dialog>
  → Side panel: <Sheet>
  → Bottom: <Drawer>
  → Confirm: <AlertDialog>

Need feedback?
  → Toast: import { toast } from 'sonner'
  → Alert: <Alert><AlertTitle/><AlertDescription/></Alert>
  → Loading: <Skeleton /> or <Spinner />

Need data display?
  → Table: <Table><TableHeader/><TableBody/></Table>
  → Card: <Card><CardHeader/><CardContent/><CardFooter/></Card>
  → Badge: <Badge variant="default|secondary|outline" />
  → Avatar: <Avatar><AvatarImage/><AvatarFallback/></Avatar>

Need navigation?
  → Desktop: <NavigationMenu /> or custom nav bar
  → Mobile: Hamburger with full-screen overlay
  → Tabs: <Tabs><TabsList><TabsTrigger/></TabsList><TabsContent/></Tabs>

Need layout?
  → Grid: grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6
  → Flex: flex flex-col lg:flex-row gap-8
  → Container: max-w-7xl mx-auto px-4 lg:px-16
```

---

## 2. COMPOSITION RULES

| Pattern | ✅ Correct | ❌ Wrong |
|---------|-----------|----------|
| Spacing | `flex gap-4` | `space-y-4` |
| Square | `size-10` | `w-10 h-10` |
| Colors | `bg-primary` | `bg-blue-500` |
| Forms | `FieldGroup > Field` | raw `div` |
| Card | `Card > CardHeader/CardContent/CardFooter` | raw `div` |
| Icons in button | `<Icon data-icon="inline-start" />` | `<Icon className="w-4 h-4" />` |

---

## 3. BUTTON VARIANTS

```html
<!-- Primary (main CTA) -->
<button class="bg-[--accent] text-white px-6 py-3 rounded-xl font-medium
               hover:brightness-110 active:scale-[0.97] transition-all duration-200">

<!-- Secondary (outline) -->
<button class="border-2 border-[--accent] text-[--accent] px-6 py-3 rounded-xl font-medium
               hover:bg-[--accent-muted] active:scale-[0.97] transition-all duration-200">

<!-- Ghost (low emphasis) -->
<button class="text-[--text-secondary] hover:text-[--text-primary]
               px-4 py-2 rounded-lg transition-colors">

<!-- Danger -->
<button class="bg-red-600 text-white px-6 py-3 rounded-xl font-medium
               hover:bg-red-700 active:scale-[0.97] transition-all duration-200">
```

---

## 4. CARD VARIANTS

### Standard Card
```html
<div class="bg-[--bg-secondary] border border-[--border] rounded-2xl p-6
            hover:shadow-md hover:-translate-y-1 transition-all duration-300">
  <h3 class="text-lg font-semibold text-[--text-primary]">Title</h3>
  <p class="text-[--text-secondary] mt-2">Description</p>
</div>
```

### Featured Card (with accent)
```html
<div class="relative bg-gradient-to-br from-[--accent]/10 to-transparent
            border border-[--accent]/20 rounded-2xl p-8
            hover:border-[--accent]/40 transition-all duration-300">
  <div class="w-12 h-12 rounded-xl bg-[--accent]/20 flex items-center justify-center mb-4">
    <svg class="w-6 h-6 text-[--accent]">...</svg>
  </div>
  <h3 class="text-xl font-bold">Featured</h3>
</div>
```

---

## 5. NAVIGATION VARIANTS

### Desktop Nav (sticky)
```html
<nav class="sticky top-0 z-50 bg-[--bg-primary]/80 backdrop-blur-lg
            border-b border-[--border]">
  <div class="max-w-7xl mx-auto px-4 lg:px-16 flex items-center justify-between h-16">
    <a href="/" class="font-bold text-lg">Logo</a>
    <div class="hidden md:flex items-center gap-8">
      <a class="text-[--text-secondary] hover:text-[--text-primary] transition-colors">Link</a>
    </div>
  </div>
</nav>
```

### Mobile Menu
```html
<div class="fixed inset-0 z-40 bg-[--bg-primary] md:hidden">
  <div class="flex flex-col p-4 gap-4">
    <a class="text-lg py-4 border-b border-[--border]">Link</a>
  </div>
</div>
```

---

## 6. FORM PATTERNS

### Login Form Structure
```html
<div class="max-w-md mx-auto">
  <h2 class="text-2xl font-bold text-center mb-8">Sign in</h2>
  <form class="flex flex-col gap-4">
    <div>
      <label class="block text-sm font-medium mb-1">Email</label>
      <input type="email" class="w-full px-4 py-3 border border-[--border] rounded-xl
             focus:outline-none focus:ring-2 focus:ring-[--accent] focus:border-[--accent]
             transition-all duration-200" />
    </div>
    <button type="submit" class="w-full bg-[--accent] text-white py-3 rounded-xl font-medium
           hover:brightness-110 active:scale-[0.97] transition-all duration-200">
      Sign in
    </button>
  </form>
</div>
```

---

## 7. RESPONSIVE PATTERNS

### Hero Section
```html
<section class="min-h-[80vh] flex items-center py-12 lg:py-24">
  <div class="max-w-7xl mx-auto px-4 lg:px-16">
    <div class="flex flex-col lg:grid lg:grid-cols-2 lg:gap-12 lg:items-center">
      <div class="order-2 lg:order-1 mt-8 lg:mt-0">
        <h1 class="text-3xl lg:text-6xl font-bold">Hero Title</h1>
        <p class="mt-4 text-base lg:text-lg text-[--text-secondary]">Description</p>
      </div>
      <div class="order-1 lg:order-2">
        <img class="w-full rounded-2xl" src="hero.jpg" alt="Hero" />
      </div>
    </div>
  </div>
</section>
```

### Feature Grid
```html
<section class="py-12 lg:py-24">
  <div class="max-w-7xl mx-auto px-4 lg:px-16">
    <h2 class="text-2xl lg:text-4xl font-bold text-center mb-12">Features</h2>
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 lg:gap-8">
      <!-- Feature cards -->
    </div>
  </div>
</section>
```

---

## 8. LOADING & EMPTY STATES

### Loading Skeleton
```html
<div class="animate-pulse space-y-4">
  <div class="h-48 bg-gray-200 rounded-2xl"></div>
  <div class="h-4 bg-gray-200 rounded w-3/4"></div>
  <div class="h-4 bg-gray-200 rounded w-1/2"></div>
</div>
```

### Empty State
```html
<div class="flex flex-col items-center justify-center py-16">
  <svg class="w-24 h-24 text-[--text-muted] mb-6">...</svg>
  <h3 class="text-xl font-semibold text-[--text-primary]">No results found</h3>
  <p class="text-[--text-secondary] mt-2">Try adjusting your search or filters</p>
  <button class="mt-6 bg-[--accent] text-white px-6 py-3 rounded-xl font-medium">Clear filters</button>
</div>
```

---

**Next:** `components/examples.md` — Full code examples
