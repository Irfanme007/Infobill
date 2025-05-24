let cartItems = [];

document.addEventListener('DOMContentLoaded', function () {
    let itemNameInput = document.getElementById('item-name');  
    let suggestionBox = document.getElementById('suggestion-box');
    let stockAvailable = 0;  // Global variable to store stock
    document.getElementById('discount').addEventListener("input", updateNetTotal);


    // Fetch product suggestions
    itemNameInput.addEventListener("input", function () {
        let query = itemNameInput.value.trim();

        if (query.length > 0) {
            fetch(`/billing/search-product/?query=${query}`)
                .then(response => response.json())
                .then(data => {
                    showSuggestions(data.products);
                })
                .catch(error => console.error('Error fetching data:', error));
        } else {
            hideSuggestions();
        }
    });

// Show product suggestions
function showSuggestions(products) {
    suggestionBox.innerHTML = '';

    if (products.length === 0) {
        hideSuggestions();
        return;
    }

    suggestionBox.style.display = 'block';
    products.forEach(product => {
        let div = document.createElement('div');
        
        // Add Tailwind CSS classes to each suggestion item
        div.classList.add(
            "suggestion-item", 
            "border-b-2",
            "cursor-pointer",  // Hand cursor on hover
            "hover:bg-gray-100", // Light background change on hover
            "hover:text-blue-600", // Text color change on hover
            "py-2", "px-4", "rounded-md", // Padding and rounded corners
            "transition-all", "duration-200" // Smooth transition for hover effect
        );
        
        div.textContent = `${product.name} (${product.brand}) ${product.sku}`;

        div.addEventListener('click', function () {
            checkIfProductInCart(product);
        });

        suggestionBox.appendChild(div);
    });
}


    // ✅ Check if product is already in the cart when selected
    function checkIfProductInCart(product) {
        let existingProduct = cartItems.find(item => item.sku === product.sku);

        if (existingProduct) {
            alert("❌ Product already in cart!");
            itemNameInput.value = "";  // Clear input
            return;
        }

        itemNameInput.value = product.name;
        document.getElementById('id_item_brand').value = product.brand;
        document.getElementById('id_unit_price').value = product.price;

        stockAvailable = product.stock; // ✅ Update stock
        document.getElementById('available').textContent = stockAvailable; // ✅ Update available field

        // ✅ Store SKU in hidden input field
        document.getElementById('product-sku').value = product.sku;
        hideSuggestions();
    }

    // Function to hide suggestions
    function hideSuggestions() {
        suggestionBox.innerHTML = "";
        suggestionBox.style.display = 'none';
    }

    // Hide suggestions when clicking outside the input or suggestion box
    document.addEventListener('click', function (event) {
        if (!itemNameInput.contains(event.target)) {
            hideSuggestions();
            document.getElementById('available').textContent = stockAvailable;
        }
    });

    // ✅ Ensure only one event listener for "Add to Bill" button
    let addToCartButton = document.getElementById("add-to-bill");

    addToCartButton.replaceWith(addToCartButton.cloneNode(true)); // Remove old event listeners
    addToCartButton = document.getElementById("add-to-bill"); // Get the fresh cloned button

    addToCartButton.addEventListener('click', validateQuantity); // Attach event only once

    function validateQuantity() {
        let name = document.getElementById("item-name").value.trim();
        let quantityInput = document.getElementById("id_quantity");
        let quantity = parseInt(quantityInput.value, 10);
        let sku = document.getElementById('product-sku').value;
        if (cartItems.some(item => item.sku === sku)) {
            alert('❌ Product already in cart!');
            return;
        }

        if (!name) {
            alert('❌ Please select a product first!');
            return;
        }

        if (isNaN(quantity) || quantity <= 0) {
            alert('❌ Quantity should be greater than 0!');
            return;
        }

        if (quantity > stockAvailable) {
            alert('❌ Not enough stock available!');
            return;
        }

        addItemToCart();
    }

    function addItemToCart() {
        let name = document.getElementById("item-name").value;
        let brand = document.getElementById("id_item_brand").value;
        let price = parseFloat(document.getElementById("id_unit_price").value);
        let quantity = parseInt(document.getElementById("id_quantity").value, 10);
        let sku = document.getElementById('product-sku').value;
        let subtotal = price * quantity;

        let item = { name, brand, price, quantity, subtotal, sku };
        cartItems.push(item);
        console.log('✅ Item added to cart', item);

        updateCartDisplay();

        // ✅ Reset input fields & set available quantity to 0
        document.getElementById("item-name").value = "";
        document.getElementById("id_item_brand").value = "";
        document.getElementById("id_unit_price").value = "";
        document.getElementById("id_quantity").value = "";
        document.getElementById("product-sku").value = "";
        stockAvailable = 0;
        document.getElementById('available').textContent = stockAvailable;
    }

    // cart functionality
    function updateCartDisplay() {
        let cartList = document.getElementById('cart-body');
        let grossTotalElement = document.getElementById('gross-total');

        cartList.innerHTML = '';
        let grossTotal = 0;

        cartItems.forEach((item, index) => {
            let row = document.createElement('tr');
            row.innerHTML = `
                <td class="px-4 py-2 text-left">${item.name} (${item.brand})</td>
                <td class="px-4 py-2 text-right">₹${item.price.toFixed(2)}</td>
                <td class="px-4 py-2 text-center">${item.quantity}</td>
                <td class="px-4 py-2 text-right">₹${item.subtotal.toFixed(2)}</td>
                <td class="px-4 py-2 text-center">
                    <button onclick="removeItem(${index})" class="bg-red-400 text-white rounded px-2 py-1 hover:bg-red-500 focus:outline-none focus:ring-2 focus:ring-red-500">
                        Remove
                    </button>
                </td>
            `;
            
            cartList.appendChild(row);
            grossTotal += item.subtotal;
        });
        grossTotalElement.textContent = grossTotal.toFixed(2);
        updateNetTotal();
    }

    window.removeItem = function (index) {
        cartItems.splice(index, 1);
        updateCartDisplay();
    };

    // net total
    function updateNetTotal() {
        let grossTotal = parseFloat(document.getElementById("gross-total").textContent);
        let discount = parseFloat(document.getElementById("discount").value) || 0;
        console.log("Inside updateNetTotal: discount =", typeof(discount));
        
        if (discount < 0) {
            alert("Discount cannot be negative!");
            document.getElementById("discount").value = 0;
            discount = 0;
        }

        if (discount > grossTotal) {
            alert("Discount cannot be more than the total!");
            document.getElementById("discount").value = grossTotal;
            discount = grossTotal;
        }

        let netTotal = grossTotal - discount;
        document.getElementById('net-total').textContent = netTotal.toFixed(2);
    }



    // sending billdata when clicked on generate invoice
    document.getElementById("generate-bill").addEventListener('click', function () {
        let customerid = document.getElementById("generate-bill").getAttribute("data-customer-id");
    
        if (cartItems.length === 0) {
            alert('❌ Cart is empty!');
            return;
        }
        if (!customerid) {
            alert('❌ Customer ID is missing!');
            return;
        }
    
        // ✅ Get discount safely
        let discountInput = document.getElementById("discount").value.trim();
        let discount = parseFloat(discountInput);
    
        // ✅ Handle invalid discount cases
        if (isNaN(discount) || discount < 0) {
            discount = 0; // Default to 0 if invalid
            console.warn("⚠️ Discount is NaN or negative. Resetting to 0.");
        }
    
        let netTotal = parseFloat(document.getElementById('net-total').textContent) || 0;
    
        console.log("📊 Sending to Django → Discount:", discount, "Net Total:", netTotal);
    
        let billData = {
            discount: discount,
            net_total: netTotal,
            items: cartItems,
        };
        console.log("📤 Sending data:", billData);
        fetch(`/billing/save-bill/${customerid}/`, {
            method: 'POST',
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": getCSRFToken()
            },
            body: JSON.stringify(billData)
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                alert("✅ Bill saved successfully!");
                window.location.href = `/billing/invoice/${data.bill_id}/`;
            } else {
                alert("❌ Error: " + data.error);
            }
        })
        .catch(error => console.error("❌ Error:", error));
    });
    
    function getCSRFToken(){
        return document.querySelector('input[name="csrfmiddlewaretoken"]').value;
    }
});
