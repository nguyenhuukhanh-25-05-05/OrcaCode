# Component Examples - Full Code Templates

> **Module:** Implementation  
> **Read Time:** 5 minutes (scan for needed component)  
> **When:** During coding phase

---

## 🎯 PURPOSE

This file contains **complete, copy-paste ready** component examples.  
Each example includes HTML + CSS (Tailwind) + JS (if needed).

---

## 1️⃣ BUTTON EXAMPLES

### Primary Button

```html
<button class="group relative px-6 py-3 
               bg-gradient-to-r from-blue-600 to-purple-600 
               rounded-xl font-medium text-white 
               shadow-lg shadow-blue-500/50
               transition-all duration-200 
               hover:shadow-xl hover:shadow-blue-500/60
               hover:-translate-y-0.5 
               active:scale-[0.97]
               focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2">
  <span class="relative z-10 flex items-center justify-center gap-2">
    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
            d="M5 13l4 4L19 7"></path>
    </svg>
    Submit
  </span>
  
  <!-- Hover overlay effect -->
  <div class="absolute inset-0 rounded-xl bg-white/20 opacity-0 
              group-hover:opacity-100 transition-opacity duration-200"></div>
</button>
```

### Secondary Button (Outline)

```html
<button class="px-6 py-3 
               border-2 border-gray-300 hover:border-gray-400
               rounded-xl font-medium text-gray-700 hover:text-gray-900
               bg-white hover:bg-gray-50
               transition-all duration-200 
               active:scale-[0.97]
               focus:outline-none focus:ring-2 focus:ring-gray-400 focus:ring-offset-2">
  Cancel
</button>
```

### Loading State

```html
<button disabled class="px-6 py-3 
                        bg-blue-600 
                        rounded-xl font-medium text-white 
                        opacity-50 cursor-not-allowed
                        flex items-center justify-center gap-2">
  <!-- Spinner -->
  <svg class="animate-spin w-5 h-5" fill="none" viewBox="0 0 24 24">
    <circle class="opacity-25" cx="12" cy="12" r="10" 
            stroke="currentColor" stroke-width="4"></circle>
    <path class="opacity-75" fill="currentColor" 
          d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
  </svg>
  Loading...
</button>
```

---

## 2️⃣ INPUT EXAMPLES

### Text Input with Floating Label

```html
<div class="relative">
  <input 
    type="text" 
    id="email" 
    class="peer w-full px-4 py-3 pt-6
           bg-white border-2 border-gray-300 rounded-xl
           text-gray-900 placeholder-transparent
           focus:outline-none focus:border-blue-500 focus:ring-4 focus:ring-blue-500/20
           transition-all duration-200"
    placeholder="Email" 
  />
  
  <label 
    for="email" 
    class="absolute left-4 top-2
           text-xs font-medium text-gray-500
           peer-placeholder-shown:text-base peer-placeholder-shown:top-3.5
           peer-focus:top-2 peer-focus:text-xs peer-focus:text-blue-500
           transition-all duration-200 pointer-events-none">
    Email address
  </label>
</div>
```

### Password Input with Visibility Toggle

```html
<div class="relative">
  <input 
    type="password" 
    id="password"
    class="w-full px-4 py-3 pr-12
           bg-white border-2 border-gray-300 rounded-xl
           text-gray-900
           focus:outline-none focus:border-blue-500 focus:ring-4 focus:ring-blue-500/20
           transition-all duration-200"
    placeholder="Password"
  />
  
  <!-- Toggle visibility button -->
  <button 
    type="button"
    class="absolute right-3 top-1/2 -translate-y-1/2
           p-2 text-gray-500 hover:text-gray-700
           transition-colors"
    aria-label="Toggle password visibility">
    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
            d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"></path>
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
            d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"></path>
    </svg>
  </button>
</div>
```

### Input with Error State

```html
<div>
  <input 
    type="email" 
    id="email-error"
    aria-invalid="true"
    aria-describedby="email-error-message"
    class="w-full px-4 py-3
           bg-white border-2 border-red-500 rounded-xl
           text-gray-900
           focus:outline-none focus:ring-4 focus:ring-red-500/20
           transition-all duration-200"
    placeholder="Email"
    value="invalid-email"
  />
  
  <p id="email-error-message" role="alert" 
     class="mt-2 text-sm text-red-600 flex items-center gap-1">
    <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
      <path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clip-rule="evenodd"></path>
    </svg>
    Please enter a valid email address
  </p>
</div>
```

---

## 3️⃣ CARD EXAMPLES

### Glass Morphism Card

```html
<div class="relative group
            bg-white/10 backdrop-blur-lg
            border border-white/20
            rounded-2xl p-6
            shadow-xl shadow-black/5
            hover:shadow-2xl hover:shadow-black/10
            hover:-translate-y-1
            transition-all duration-300">
  
  <!-- Gradient glow on hover -->
  <div class="absolute inset-0 rounded-2xl opacity-0 group-hover:opacity-100 
              bg-gradient-to-br from-blue-500/20 to-purple-500/20 
              transition-opacity duration-300 -z-10 blur-xl"></div>
  
  <!-- Icon -->
  <div class="w-12 h-12 rounded-xl bg-gradient-to-br from-blue-500 to-purple-600
              flex items-center justify-center mb-4
              shadow-lg shadow-blue-500/50">
    <svg class="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
            d="M13 10V3L4 14h7v7l9-11h-7z"></path>
    </svg>
  </div>
  
  <!-- Content -->
  <h3 class="text-xl font-bold text-white mb-2">
    Feature Title
  </h3>
  <p class="text-white/70 leading-relaxed">
    Beautiful glass morphism card with gradient glow effect on hover.
    Perfect for feature showcases.
  </p>
</div>
```

### Standard Card with Hover Effect

```html
<div class="bg-white border border-gray-200 rounded-2xl p-6
            shadow-sm hover:shadow-md
            hover:border-gray-300
            transition-all duration-300">
  
  <div class="flex items-start justify-between mb-4">
    <h3 class="text-lg font-semibold text-gray-900">
      Card Title
    </h3>
    <span class="px-3 py-1 text-xs font-medium text-green-700 bg-green-100 
                 rounded-full">
      Active
    </span>
  </div>
  
  <p class="text-gray-600 mb-4">
    Card description goes here. This is a standard card design with subtle
    hover effects and clean typography.
  </p>
  
  <div class="flex items-center justify-between pt-4 border-t border-gray-100">
    <span class="text-sm text-gray-500">
      Updated 2 hours ago
    </span>
    <button class="text-blue-600 hover:text-blue-700 font-medium text-sm
                   transition-colors">
      View details →
    </button>
  </div>
</div>
```

---

## 4️⃣ MODAL/DIALOG EXAMPLES

### Modal with Backdrop Blur

```html
<!-- Backdrop -->
<div class="fixed inset-0 z-50 
            bg-black/50 backdrop-blur-sm
            flex items-center justify-center p-4
            animate-in fade-in duration-200">
  
  <!-- Modal -->
  <div class="bg-white rounded-2xl shadow-2xl
              w-full max-w-md
              animate-in zoom-in-95 duration-200"
       role="dialog"
       aria-labelledby="modal-title"
       aria-modal="true">
    
    <!-- Header -->
    <div class="flex items-center justify-between p-6 border-b border-gray-100">
      <h2 id="modal-title" class="text-xl font-bold text-gray-900">
        Confirm Action
      </h2>
      <button class="p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-100 
                     rounded-lg transition-colors"
              aria-label="Close dialog">
        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
                d="M6 18L18 6M6 6l12 12"></path>
        </svg>
      </button>
    </div>
    
    <!-- Content -->
    <div class="p-6">
      <p class="text-gray-600">
        Are you sure you want to proceed? This action cannot be undone.
      </p>
    </div>
    
    <!-- Footer -->
    <div class="flex items-center justify-end gap-3 p-6 border-t border-gray-100">
      <button class="px-4 py-2 border border-gray-300 rounded-lg
                     text-gray-700 hover:bg-gray-50
                     transition-colors">
        Cancel
      </button>
      <button class="px-4 py-2 bg-red-600 hover:bg-red-700 rounded-lg
                     text-white font-medium
                     transition-colors">
        Confirm
      </button>
    </div>
  </div>
</div>
```

---

## 5️⃣ NAVBAR EXAMPLES

### Sticky Navbar with Blur

```html
<nav class="sticky top-0 z-50 
            backdrop-blur-lg bg-white/80 
            border-b border-gray-200/50
            transition-all duration-300">
  
  <div class="max-w-7xl mx-auto px-4">
    <div class="flex items-center justify-between h-16">
      
      <!-- Logo -->
      <a href="/" class="flex items-center gap-2 group">
        <div class="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-600 to-purple-600
                    flex items-center justify-center
                    transition-transform group-hover:scale-110">
          <svg class="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
                  d="M13 10V3L4 14h7v7l9-11h-7z"></path>
          </svg>
        </div>
        <span class="font-bold text-lg text-gray-900">Brand</span>
      </a>
      
      <!-- Desktop Navigation -->
      <div class="hidden md:flex items-center gap-8">
        <a href="#features" 
           class="text-gray-600 hover:text-gray-900
                  relative after:absolute after:bottom-0 after:left-0 after:w-0 after:h-0.5
                  after:bg-blue-600 after:transition-all hover:after:w-full
                  transition-colors">
          Features
        </a>
        <a href="#pricing" 
           class="text-gray-600 hover:text-gray-900
                  relative after:absolute after:bottom-0 after:left-0 after:w-0 after:h-0.5
                  after:bg-blue-600 after:transition-all hover:after:w-full
                  transition-colors">
          Pricing
        </a>
        <a href="#about" 
           class="text-gray-600 hover:text-gray-900
                  relative after:absolute after:bottom-0 after:left-0 after:w-0 after:h-0.5
                  after:bg-blue-600 after:transition-all hover:after:w-full
                  transition-colors">
          About
        </a>
      </div>
      
      <!-- CTA Button -->
      <div class="hidden md:flex items-center gap-4">
        <a href="#" class="text-gray-600 hover:text-gray-900 transition-colors">
          Sign in
        </a>
        <a href="#" class="px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg
                          text-white font-medium
                          transition-colors">
          Get Started
        </a>
      </div>
      
      <!-- Mobile Menu Button -->
      <button class="md:hidden p-2 text-gray-600 hover:text-gray-900 hover:bg-gray-100
                     rounded-lg transition-colors"
              aria-label="Toggle menu">
        <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
                d="M4 6h16M4 12h16M4 18h16"></path>
        </svg>
      </button>
    </div>
  </div>
</nav>
```

---

## 6️⃣ FORM EXAMPLES

### Complete Login Form

```html
<div class="min-h-screen flex items-center justify-center p-4
            bg-gradient-to-br from-blue-50 to-purple-50">
  
  <!-- Glassmorphism Card -->
  <div class="w-full max-w-md
              bg-white/80 backdrop-blur-lg
              border border-white/20
              rounded-2xl shadow-2xl p-8">
    
    <!-- Logo -->
    <div class="flex justify-center mb-8">
      <div class="w-16 h-16 rounded-2xl bg-gradient-to-br from-blue-600 to-purple-600
                  flex items-center justify-center shadow-lg shadow-blue-500/50">
        <svg class="w-8 h-8 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
                d="M13 10V3L4 14h7v7l9-11h-7z"></path>
        </svg>
      </div>
    </div>
    
    <!-- Title -->
    <h2 class="text-2xl font-bold text-center text-gray-900 mb-2">
      Welcome back
    </h2>
    <p class="text-center text-gray-600 mb-8">
      Sign in to your account to continue
    </p>
    
    <!-- Form -->
    <form class="flex flex-col gap-4">
      
      <!-- Email Input -->
      <div class="relative">
        <input 
          type="email" 
          id="email" 
          class="peer w-full px-4 py-3 pt-6
                 bg-white border-2 border-gray-300 rounded-xl
                 text-gray-900 placeholder-transparent
                 focus:outline-none focus:border-blue-500 focus:ring-4 focus:ring-blue-500/20
                 transition-all duration-200"
          placeholder="Email" 
          required
        />
        <label 
          for="email" 
          class="absolute left-4 top-2
                 text-xs font-medium text-gray-500
                 peer-placeholder-shown:text-base peer-placeholder-shown:top-3.5
                 peer-focus:top-2 peer-focus:text-xs peer-focus:text-blue-500
                 transition-all duration-200 pointer-events-none">
          Email address
        </label>
      </div>
      
      <!-- Password Input -->
      <div class="relative">
        <input 
          type="password" 
          id="password"
          class="w-full px-4 py-3 pr-12
                 bg-white border-2 border-gray-300 rounded-xl
                 text-gray-900
                 focus:outline-none focus:border-blue-500 focus:ring-4 focus:ring-blue-500/20
                 transition-all duration-200"
          placeholder="Password"
          required
        />
        <button 
          type="button"
          class="absolute right-3 top-1/2 -translate-y-1/2
                 p-2 text-gray-500 hover:text-gray-700
                 transition-colors"
          aria-label="Toggle password visibility">
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
                  d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"></path>
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
                  d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"></path>
          </svg>
        </button>
      </div>
      
      <!-- Remember & Forgot -->
      <div class="flex items-center justify-between">
        <label class="flex items-center gap-2 cursor-pointer">
          <input type="checkbox" class="w-4 h-4 rounded border-gray-300
                                         text-blue-600 focus:ring-2 focus:ring-blue-500">
          <span class="text-sm text-gray-600">Remember me</span>
        </label>
        <a href="#" class="text-sm text-blue-600 hover:text-blue-700 font-medium">
          Forgot password?
        </a>
      </div>
      
      <!-- Submit Button -->
      <button type="submit" 
              class="group relative w-full px-6 py-3 mt-2
                     bg-gradient-to-r from-blue-600 to-purple-600 
                     rounded-xl font-medium text-white 
                     shadow-lg shadow-blue-500/50
                     transition-all duration-200 
                     hover:shadow-xl hover:shadow-blue-500/60
                     hover:-translate-y-0.5 
                     active:scale-[0.97]
                     focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2">
        <span class="relative z-10">Sign in</span>
        <div class="absolute inset-0 rounded-xl bg-white/20 opacity-0 
                    group-hover:opacity-100 transition-opacity duration-200"></div>
      </button>
    </form>
    
    <!-- Divider -->
    <div class="relative my-8">
      <div class="absolute inset-0 flex items-center">
        <div class="w-full border-t border-gray-300"></div>
      </div>
      <div class="relative flex justify-center text-sm">
        <span class="px-4 bg-white/80 text-gray-500">Or continue with</span>
      </div>
    </div>
    
    <!-- Social Login -->
    <div class="grid grid-cols-2 gap-3">
      <button class="flex items-center justify-center gap-2 px-4 py-3
                     bg-white border-2 border-gray-300 rounded-xl
                     text-gray-700 font-medium
                     hover:bg-gray-50 hover:border-gray-400
                     transition-all active:scale-[0.97]">
        <svg class="w-5 h-5" viewBox="0 0 24 24">
          <path fill="currentColor" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
          <path fill="currentColor" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
          <path fill="currentColor" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
          <path fill="currentColor" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
        </svg>
        Google
      </button>
      <button class="flex items-center justify-center gap-2 px-4 py-3
                     bg-white border-2 border-gray-300 rounded-xl
                     text-gray-700 font-medium
                     hover:bg-gray-50 hover:border-gray-400
                     transition-all active:scale-[0.97]">
        <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
          <path d="M12 2C6.477 2 2 6.477 2 12c0 4.42 2.865 8.17 6.839 9.49.5.092.682-.217.682-.482 0-.237-.008-.866-.013-1.7-2.782.603-3.369-1.34-3.369-1.34-.454-1.156-1.11-1.463-1.11-1.463-.908-.62.069-.608.069-.608 1.003.07 1.531 1.03 1.531 1.03.892 1.529 2.341 1.087 2.91.831.092-.646.35-1.086.636-1.336-2.22-.253-4.555-1.11-4.555-4.943 0-1.091.39-1.984 1.029-2.683-.103-.253-.446-1.27.098-2.647 0 0 .84-.269 2.75 1.025A9.578 9.578 0 0112 6.836c.85.004 1.705.114 2.504.336 1.909-1.294 2.747-1.025 2.747-1.025.546 1.377.203 2.394.1 2.647.64.699 1.028 1.592 1.028 2.683 0 3.842-2.339 4.687-4.566 4.935.359.309.678.919.678 1.852 0 1.336-.012 2.415-.012 2.743 0 .267.18.578.688.48C19.138 20.167 22 16.418 22 12c0-5.523-4.477-10-10-10z"/>
        </svg>
        GitHub
      </button>
    </div>
    
    <!-- Sign up link -->
    <p class="text-center text-sm text-gray-600 mt-8">
      Don't have an account?
      <a href="#" class="text-blue-600 hover:text-blue-700 font-medium">
        Sign up
      </a>
    </p>
  </div>
</div>
```

---

## 💡 USAGE TIPS

1. **Copy the entire block** - Don't cherry-pick classes, copy the full example
2. **Adjust colors** - Replace blue-* with your brand color
3. **Add functionality** - Wire up event handlers for buttons/forms
4. **Test responsive** - Check mobile/tablet/desktop views
5. **Verify accessibility** - Ensure ARIA labels and focus states work

---

**See Also:**
- `components/patterns.md` - When to use which component
- `design/colors.md` - Color palette system
- `animation/rules.md` - Animation guidelines

---

## 7️⃣ STYLE VARIETY — DIFFERENT DESIGN LANGUAGES

> **CRITICAL:** Do NOT use the blue-purple glassmorphism style for every project.
> Below are examples in different styles. Pick one that matches the task.

---

### A. Apple-Style Premium (White + Light Gray + Blue)

```html
<nav class="sticky top-0 z-50 bg-white/90 backdrop-blur-xl border-b border-[#D2D2D7]">
  <div class="max-w-7xl mx-auto px-4 lg:px-16">
    <div class="flex items-center justify-between h-12 lg:h-16">
      <a href="/" class="text-xl font-semibold text-[#1D1D1F] tracking-tight">Product</a>
      <div class="hidden md:flex items-center gap-10">
        <a class="text-sm text-[#6E6E73] hover:text-[#1D1D1F] transition-colors">Mac</a>
        <a class="text-sm text-[#6E6E73] hover:text-[#1D1D1F] transition-colors">iPad</a>
        <a class="text-sm text-[#6E6E73] hover:text-[#1D1D1F] transition-colors">iPhone</a>
        <a class="text-sm text-[#6E6E73] hover:text-[#1D1D1F] transition-colors">Support</a>
      </div>
      <button class="text-sm text-[#0071E3] hover:underline">Shop</button>
    </div>
  </div>
</nav>

<section class="py-16 lg:py-24">
  <div class="max-w-7xl mx-auto px-4 lg:px-16">
    <div class="flex flex-col lg:grid lg:grid-cols-2 lg:gap-16 items-center">
      <div>
        <p class="text-sm font-medium text-[#6E6E73] uppercase tracking-wider mb-4">New</p>
        <h1 class="text-4xl lg:text-6xl font-bold text-[#1D1D1F] tracking-tight leading-tight">
          Premium Product. Designed to impress.
        </h1>
        <p class="text-base lg:text-lg text-[#6E6E73] mt-6 leading-relaxed max-w-lg">
          From $999 or $41.62/mo. for 24 mo. before trade-in.
        </p>
        <div class="flex gap-4 mt-8">
          <a class="inline-block bg-[#0071E3] text-white text-sm font-medium px-8 py-3 rounded-full
                    hover:brightness-110 transition-all duration-200 active:scale-[0.97]">
            Buy
          </a>
          <a class="inline-block text-[#0071E3] text-sm font-medium hover:underline mt-3">
            Learn more >
          </a>
        </div>
      </div>
      <div class="mt-12 lg:mt-0">
        <img src="https://placehold.co/600x500/f5f5f7/1d1d1f?text=Product"
             alt="Product" class="w-full rounded-2xl shadow-xl" />
      </div>
    </div>
  </div>
</section>
```

---

### B. Linear-Style Dark (Dark + Purple Accent)

```html
<div class="min-h-screen bg-[#17171A]">
  <nav class="border-b border-[#2A2A2E]">
    <div class="max-w-7xl mx-auto px-4 lg:px-16 flex items-center justify-between h-14">
      <span class="text-white font-semibold">linear</span>
      <div class="hidden md:flex items-center gap-8">
        <a class="text-sm text-[#8A8F99] hover:text-white transition-colors">Features</a>
        <a class="text-sm text-[#8A8F99] hover:text-white transition-colors">Changelog</a>
        <a class="text-sm text-[#8A8F99] hover:text-white transition-colors">Pricing</a>
      </div>
      <button class="text-sm bg-[#5E6AD2] text-white px-4 py-2 rounded-lg
                     hover:bg-[#4F5BCA] transition-colors">Sign in</button>
    </div>
  </nav>

  <section class="py-20 lg:py-32 px-4">
    <div class="max-w-3xl mx-auto text-center">
      <h1 class="text-4xl lg:text-6xl font-bold text-white tracking-tight leading-tight">
        Build better products
      </h1>
      <p class="text-[#8A8F99] text-lg mt-6 max-w-xl mx-auto leading-relaxed">
        Linear is a purpose-built tool for planning and building products.
      </p>
      <div class="flex justify-center gap-4 mt-10">
        <a class="bg-[#5E6AD2] text-white px-8 py-3 rounded-lg font-medium text-sm
                  hover:bg-[#4F5BCA] transition-colors">Start free trial</a>
        <a class="text-[#8A8F99] text-sm py-3 px-2 hover:text-white transition-colors">
          Watch demo →
        </a>
      </div>
    </div>
  </section>
</div>
```

---

### C. Dior-Style Luxury (Champagne + Gold)

```html
<div class="min-h-screen bg-[#F8F5F0]">
  <nav class="border-b border-[#E5DDD3]">
    <div class="max-w-7xl mx-auto px-4 lg:px-16 flex items-center justify-center h-16">
      <span class="text-2xl font-serif italic text-[#1C1C1E]">Dior</span>
    </div>
    <div class="hidden md:flex justify-center gap-12 pb-4">
      <a class="text-xs uppercase tracking-[0.15em] text-[#8E8E93] hover:text-[#1C1C1E] transition-colors">Fragrance</a>
      <a class="text-xs uppercase tracking-[0.15em] text-[#8E8E93] hover:text-[#1C1C1E] transition-colors">Makeup</a>
      <a class="text-xs uppercase tracking-[0.15em] text-[#8E8E93] hover:text-[#1C1C1E] transition-colors">Skincare</a>
    </div>
  </nav>

  <section class="py-24 px-4">
    <div class="max-w-4xl mx-auto text-center">
      <div class="w-16 h-[1px] bg-[#A67C52] mx-auto mb-8"></div>
      <p class="text-sm uppercase tracking-[0.2em] text-[#A67C52] mb-6">New Collection</p>
      <h1 class="text-5xl lg:text-7xl font-serif text-[#1C1C1E] tracking-tight leading-tight">
        The Art of Luxury
      </h1>
      <p class="text-[#8E8E93] text-lg mt-6 max-w-lg mx-auto leading-relaxed font-light">
        Discover our latest fragrance, crafted with the finest ingredients.
      </p>
      <div class="w-16 h-[1px] bg-[#A67C52] mx-auto mt-12 mb-8"></div>
      <a class="inline-block text-sm uppercase tracking-[0.15em] text-white bg-[#1C1C1E]
                px-10 py-4 hover:bg-[#333] transition-colors duration-300">
        Discover
      </a>
    </div>
  </section>
</div>
```

---

### D. Stripe-Style SaaS (White + Ice Blue + Purple)

```html
<div class="min-h-screen bg-[#F6F9FC]">
  <nav class="bg-white border-b border-[#E6EBF1]">
    <div class="max-w-7xl mx-auto px-4 lg:px-16 flex items-center justify-between h-14">
      <span class="text-lg font-semibold text-[#1A1A2E]">stripe</span>
      <div class="hidden md:flex items-center gap-8">
        <a class="text-sm text-[#6B7C93] hover:text-[#1A1A2E] transition-colors">Products</a>
        <a class="text-sm text-[#6B7C93] hover:text-[#1A1A2E] transition-colors">Developers</a>
        <a class="text-sm text-[#6B7C93] hover:text-[#1A1A2E] transition-colors">Pricing</a>
      </div>
      <button class="text-sm bg-[#635BFF] text-white px-5 py-2 rounded-lg font-medium
                     hover:bg-[#4F46E5] transition-colors">Sign in</button>
    </div>
  </nav>

  <section class="py-16 lg:py-24 px-4">
    <div class="max-w-7xl mx-auto">
      <div class="flex flex-col lg:grid lg:grid-cols-2 lg:gap-16 items-center">
        <div>
          <h1 class="text-4xl lg:text-6xl font-bold text-[#1A1A2E] tracking-tight leading-tight">
            Payments infrastructure for the internet
          </h1>
          <p class="text-[#6B7C93] text-lg mt-6 leading-relaxed">
            Millions of companies use Stripe to accept payments online.
          </p>
          <div class="flex gap-4 mt-8">
            <a class="bg-[#635BFF] text-white px-8 py-3 rounded-lg font-medium text-sm
                      hover:bg-[#4F46E5] transition-all duration-200 active:scale-[0.97]">
              Start now
            </a>
            <a class="text-sm text-[#635BFF] font-medium py-3 hover:text-[#4F46E5] transition-colors">
              Contact sales →
            </a>
          </div>
        </div>
        <div class="mt-12 lg:mt-0">
          <div class="bg-white rounded-2xl shadow-xl shadow-[#635BFF]/10 border border-[#E6EBF1] p-8">
            <div class="flex items-center justify-between mb-6">
              <span class="text-sm text-[#6B7C93]">Monthly revenue</span>
              <span class="text-2xl font-bold text-[#1A1A2E]">$128,430</span>
            </div>
            <div class="h-2 bg-[#E6EBF1] rounded-full mb-2">
              <div class="h-2 w-3/4 bg-gradient-to-r from-[#635BFF] to-[#00D4AA] rounded-full"></div>
            </div>
            <p class="text-xs text-[#6B7C93]">↑ 23% from last month</p>
          </div>
        </div>
      </div>
    </div>
  </section>
</div>
```

---

### E. Shopify-Style Cinematic (Dark Teal + Lime)

```html
<div class="min-h-screen bg-[#00282B]">
  <nav class="border-b border-[#1A4D50]">
    <div class="max-w-7xl mx-auto px-4 lg:px-16 flex items-center justify-between h-16">
      <span class="text-white text-xl font-bold tracking-tight">shopify</span>
      <div class="hidden md:flex items-center gap-8">
        <a class="text-sm text-[#B8D4D6] hover:text-white transition-colors">Start</a>
        <a class="text-sm text-[#B8D4D6] hover:text-white transition-colors">Sell</a>
        <a class="text-sm text-[#B8D4D6] hover:text-white transition-colors">Market</a>
        <a class="text-sm text-[#B8D4D6] hover:text-white transition-colors">Manage</a>
      </div>
      <button class="text-sm bg-[#95BF47] text-[#00282B] px-5 py-2.5 rounded-lg font-bold
                     hover:bg-[#A8D05A] transition-colors">Start free trial</button>
    </div>
  </nav>

  <section class="relative min-h-[80vh] flex items-center">
    <div class="absolute inset-0 bg-[radial-gradient(ellipse_at_center,rgba(149,191,71,0.15)_0%,transparent_70%)]"></div>
    <div class="relative max-w-7xl mx-auto px-4 lg:px-16 py-20">
      <div class="max-w-3xl">
        <p class="text-[#95BF47] text-sm uppercase tracking-[0.15em] font-bold mb-6">Ecommerce platform</p>
        <h1 class="text-5xl lg:text-7xl font-bold text-white tracking-tight leading-tight">
          Anyone can sell<br/>anything online
        </h1>
        <p class="text-[#B8D4D6] text-lg mt-6 max-w-xl leading-relaxed">
          Start your free 14-day trial. No credit card required.
        </p>
        <div class="flex gap-3 mt-10">
          <a class="bg-[#95BF47] text-[#00282B] px-8 py-3 rounded-lg font-bold text-sm
                    hover:bg-[#A8D05A] transition-all duration-200 active:scale-[0.97]">
            Start free trial
          </a>
        </div>
      </div>
    </div>
  </section>
</div>
```

---

### F. Spotify-Style Dark (Green + Duotone)

```html
<div class="min-h-screen bg-[#121212]">
  <nav class="bg-[#121212] border-b border-[#282828]">
    <div class="max-w-7xl mx-auto px-4 lg:px-16 flex items-center justify-between h-16">
      <span class="text-white text-2xl font-bold">Spotify</span>
      <div class="hidden md:flex items-center gap-8">
        <a class="text-sm text-[#B3B3B3] hover:text-white font-medium transition-colors">Premium</a>
        <a class="text-sm text-[#B3B3B3] hover:text-white font-medium transition-colors">Support</a>
        <a class="text-sm text-[#B3B3B3] hover:text-white font-medium transition-colors">Download</a>
      </div>
    </div>
  </nav>

  <section class="px-4 py-16 lg:py-24">
    <div class="max-w-7xl mx-auto">
      <h1 class="text-4xl lg:text-6xl font-bold text-white tracking-tight text-center">
        Listening is everything
      </h1>
      <p class="text-[#B3B3B3] text-center mt-4 text-lg">Millions of songs and podcasts. No credit card needed.</p>
      <div class="flex justify-center mt-8">
        <a class="bg-[#1DB954] text-black font-bold px-8 py-4 rounded-full text-sm
                  hover:bg-[#1ED760] hover:scale-105 transition-all duration-200 active:scale-[0.97]">
          Get Spotify Free
        </a>
      </div>
      <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4 mt-16">
        <div class="bg-[#1E3264] rounded-lg p-4 aspect-square flex items-end">
          <span class="text-white font-bold text-lg">Pop</span>
        </div>
        <div class="bg-[#E13300] rounded-lg p-4 aspect-square flex items-end">
          <span class="text-white font-bold text-lg">Hip-Hop</span>
        </div>
        <div class="bg-[#608108] rounded-lg p-4 aspect-square flex items-end">
          <span class="text-white font-bold text-lg">Rock</span>
        </div>
        <div class="bg-[#BA5D07] rounded-lg p-4 aspect-square flex items-end">
          <span class="text-white font-bold text-lg">Indie</span>
        </div>
      </div>
    </div>
  </section>
</div>
```

---

## 8️⃣ COMPLETE LANDING PAGE EXAMPLE (Mixed Style)

This section shows a full landing page using **Palette B (Stripe)** + **Typography Pairing 9 (Cabinet Grotesk + Inter)**:

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Product — Beautiful SaaS Landing</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
  <script src="https://cdn.tailwindcss.com"></script>
  <style>
    :root {
      --bg-primary: #FFFFFF;
      --bg-secondary: #F6F9FC;
      --text-primary: #1A1A2E;
      --text-secondary: #6B7C93;
      --accent: #635BFF;
      --accent-hover: #4F46E5;
      --border: #E6EBF1;
    }
    * { transition: transform 200ms cubic-bezier(0.23, 1, 0.32, 1),
                   opacity 200ms cubic-bezier(0.23, 1, 0.32, 1),
                   background-color 200ms ease,
                   border-color 200ms ease; }
    @media (prefers-reduced-motion: reduce) {
      * { animation-duration: 0.01ms !important; transition-duration: 0.01ms !important; }
    }
  </style>
</head>
<body class="font-['Inter'] bg-[--bg-primary] text-[--text-primary] antialiased">

  <!-- Navigation -->
  <nav class="sticky top-0 z-50 bg-[--bg-primary]/80 backdrop-blur-lg border-b border-[--border]">
    <div class="max-w-7xl mx-auto px-4 lg:px-16 flex items-center justify-between h-14">
      <span class="font-bold text-lg">Product</span>
      <div class="hidden md:flex items-center gap-8">
        <a class="text-sm text-[--text-secondary] hover:text-[--text-primary] transition-colors">Features</a>
        <a class="text-sm text-[--text-secondary] hover:text-[--text-primary] transition-colors">Pricing</a>
        <a class="text-sm text-[--text-secondary] hover:text-[--text-primary] transition-colors">About</a>
      </div>
      <button class="text-sm bg-[--accent] text-white px-5 py-2 rounded-lg font-medium
                     hover:bg-[--accent-hover] active:scale-[0.97]">Get Started</button>
    </div>
  </nav>

  <!-- Hero -->
  <section class="relative min-h-[80vh] flex items-center overflow-hidden">
    <div class="absolute inset-0 bg-gradient-to-br from-[--accent]/5 via-transparent to-transparent"></div>
    <div class="relative max-w-7xl mx-auto px-4 lg:px-16 py-16 lg:py-24">
      <div class="flex flex-col lg:grid lg:grid-cols-2 lg:gap-16 items-center">
        <div>
          <p class="text-sm font-medium text-[--accent] uppercase tracking-wider mb-4">Launching 2026</p>
          <h1 class="text-4xl lg:text-6xl font-bold tracking-tight leading-tight">
            Build faster. Ship smarter.
          </h1>
          <p class="text-[--text-secondary] text-lg mt-6 leading-relaxed max-w-lg">
            The all-in-one platform for modern teams to build, ship, and scale products.
          </p>
          <div class="flex flex-col sm:flex-row gap-3 mt-8">
            <a class="inline-flex items-center justify-center bg-[--accent] text-white px-8 py-3
                      rounded-lg font-medium text-sm hover:bg-[--accent-hover] active:scale-[0.97]">
              Start free trial
            </a>
            <a class="inline-flex items-center justify-center border border-[--border] text-[--text-secondary]
                      px-8 py-3 rounded-lg font-medium text-sm hover:border-[--text-secondary] transition-colors">
              Watch demo
            </a>
          </div>
        </div>
        <div class="mt-12 lg:mt-0">
          <div class="bg-white rounded-2xl shadow-2xl shadow-[--accent]/10 border border-[--border] p-6 lg:p-8">
            <div class="flex items-center justify-between mb-8">
              <span class="text-sm font-medium">Dashboard</span>
              <span class="text-xs text-[--text-secondary] bg-[--bg-secondary] px-3 py-1 rounded-full">Live</span>
            </div>
            <div class="space-y-4">
              <div class="flex items-center justify-between p-4 bg-[--bg-secondary] rounded-xl">
                <span class="text-sm">Total Revenue</span>
                <span class="font-bold text-lg">$84,250</span>
              </div>
              <div class="flex items-center justify-between p-4 bg-[--bg-secondary] rounded-xl">
                <span class="text-sm">Active Users</span>
                <span class="font-bold text-lg">12,430</span>
              </div>
              <div class="flex items-center justify-between p-4 bg-[--bg-secondary] rounded-xl">
                <span class="text-sm">Conversion</span>
                <span class="font-bold text-lg text-green-600">↑ 8.2%</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </section>

  <!-- Features Grid -->
  <section class="py-16 lg:py-24 bg-[--bg-secondary]">
    <div class="max-w-7xl mx-auto px-4 lg:px-16">
      <div class="text-center mb-12 lg:mb-16">
        <h2 class="text-2xl lg:text-4xl font-bold tracking-tight">Everything you need</h2>
        <p class="text-[--text-secondary] mt-4 max-w-lg mx-auto">All the tools your team needs in one platform.</p>
      </div>
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 lg:gap-8">
        <div class="bg-white rounded-2xl border border-[--border] p-6 hover:shadow-lg hover:-translate-y-1 transition-all duration-300">
          <div class="w-10 h-10 rounded-lg bg-[--accent]/10 flex items-center justify-center mb-4">
            <svg class="w-5 h-5 text-[--accent]" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"/></svg>
          </div>
          <h3 class="font-semibold text-lg mb-2">Lightning Fast</h3>
          <p class="text-sm text-[--text-secondary] leading-relaxed">Built for speed. Pages load in milliseconds.</p>
        </div>
        <div class="bg-white rounded-2xl border border-[--border] p-6 hover:shadow-lg hover:-translate-y-1 transition-all duration-300">
          <div class="w-10 h-10 rounded-lg bg-[--accent]/10 flex items-center justify-center mb-4">
            <svg class="w-5 h-5 text-[--accent]" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"/></svg>
          </div>
          <h3 class="font-semibold text-lg mb-2">Enterprise Security</h3>
          <p class="text-sm text-[--text-secondary] leading-relaxed">SOC 2 compliant. End-to-end encrypted.</p>
        </div>
        <div class="bg-white rounded-2xl border border-[--border] p-6 hover:shadow-lg hover:-translate-y-1 transition-all duration-300">
          <div class="w-10 h-10 rounded-lg bg-[--accent]/10 flex items-center justify-center mb-4">
            <svg class="w-5 h-5 text-[--accent]" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z"/></svg>
          </div>
          <h3 class="font-semibold text-lg mb-2">Team Collaboration</h3>
          <p class="text-sm text-[--text-secondary] leading-relaxed">Real-time sync across your entire team.</p>
        </div>
      </div>
    </div>
  </section>

  <!-- Footer -->
  <footer class="bg-[#1A1A2E] text-white py-12">
    <div class="max-w-7xl mx-auto px-4 lg:px-16">
      <div class="grid grid-cols-2 md:grid-cols-4 gap-8">
        <div><h4 class="font-semibold text-sm mb-4">Product</h4><a class="block text-sm text-white/60 hover:text-white py-1">Features</a></div>
        <div><h4 class="font-semibold text-sm mb-4">Company</h4><a class="block text-sm text-white/60 hover:text-white py-1">About</a></div>
        <div><h4 class="font-semibold text-sm mb-4">Resources</h4><a class="block text-sm text-white/60 hover:text-white py-1">Docs</a></div>
        <div><h4 class="font-semibold text-sm mb-4">Legal</h4><a class="block text-sm text-white/60 hover:text-white py-1">Privacy</a></div>
      </div>
      <div class="border-t border-white/10 mt-8 pt-8 text-sm text-white/40 text-center">
        &copy; 2026 Product. All rights reserved.
      </div>
    </div>
  </footer>

</body>
</html>
```

---

## 💡 HOW TO USE THESE EXAMPLES

| If task is... | Use example... | Then customize... |
|---------------|---------------|-------------------|
| Premium product landing | Apple (A) | Change blue to brand color |
| Dev tool / Dashboard | Linear (B) | Adjust purple shade |
| Luxury / Fashion brand | Dior (C) | Replace gold accent |
| SaaS / B2B platform | Stripe (D) | Swap purple for brand color |
| E-commerce / Startup | Shopify (E) | Change lime green |
| Media / Entertainment | Spotify (F) | Pick duotone images |
| Full landing page | Complete (8) | Map colors to chosen palette |

**CRITICAL: Never copy-paste without adapting colors and fonts to the project.**
